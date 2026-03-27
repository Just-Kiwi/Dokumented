"""
Main extraction pipeline orchestrating all components.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from db.models import ScriptLibrary, ExtractionResult, StatusEnum
from agents.llm_agent import LLMAgent
from agents.dllm_checker import dLLMChecker
from services.script_runner import ScriptRunner
from exceptions import AnthropicCreditError, MercuryCreditError, APIError
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


class FingerprintError(PipelineError):
    """Failed to generate document fingerprint."""
    pass


class ScriptGenerationError(PipelineError):
    """Failed to generate extraction script."""
    pass


class ScriptExecutionError(PipelineError):
    """Failed to execute extraction script."""
    pass


class ValidationError(PipelineError):
    """Failed to validate fields with dLLM."""
    pass


class ExtractionPipeline:
    """Orchestrates the full extraction flow with retry logic and human escalation."""

    def __init__(self, db: Session, llm_api_key: Optional[str] = None, 
                 dllm_api_key: Optional[str] = None, dllm_base_url: Optional[str] = None):
        """Initialize pipeline with database and agent clients."""
        self.db = db
        self.llm_agent = LLMAgent(api_key=llm_api_key)
        self.dllm_checker = dLLMChecker(api_key=dllm_api_key, base_url=dllm_base_url)
        self.script_runner = ScriptRunner()
        self.max_retries = 3
        self.confidence_threshold = 0.75

    async def extract(self, filename: str, raw_text: str, schema: List[Dict],
                     events_callback=None) -> int:
        """
        Full extraction pipeline. Returns the extraction_result id.
        
        Events emitted:
        - fingerprint_assigned
        - script_found / script_written
        - script_executed
        - dllm_check_complete
        - retry / escalated_to_human / complete
        - error
        """
        
        def emit(event: str, data: Dict = None):
            """Emit WebSocket event."""
            if events_callback:
                events_callback({"event": event, "data": data or {}})

        fingerprint = None
        script = None
        extracted_json = {}
        dllm_report = {}
        missing_fields = []
        
        try:
            # Step 1: Fingerprint
            logger.info(f"Starting extraction for {filename}")
            try:
                fingerprint = self.llm_agent.fingerprint(raw_text)
                emit("fingerprint_assigned", {"fingerprint": fingerprint})
                logger.info(f"Fingerprint generated: {fingerprint}")
            except AnthropicCreditError as e:
                emit("error", {"step": "fingerprint", "error": str(e)})
                raise
            except Exception as e:
                logger.error(f"Fingerprint generation failed: {e}")
                emit("error", {"step": "fingerprint", "error": str(e)})
                raise FingerprintError(f"Failed to generate fingerprint: {e}")

            # Step 2: Script lookup or creation
            try:
                script = self.db.query(ScriptLibrary).filter_by(fingerprint=fingerprint).first()
                
                if script:
                    emit("script_found", {"version": script.version})
                    logger.info(f"Found existing script v{script.version}")
                else:
                    script_body = self.llm_agent.write_script(raw_text, schema, fingerprint)
                    script = ScriptLibrary(
                        fingerprint=fingerprint,
                        script_body=script_body,
                        version=1
                    )
                    self.db.add(script)
                    self.db.commit()
                    self.db.refresh(script)
                    emit("script_written", {"version": script.version})
                    logger.info(f"Created new script v{script.version}")
            except AnthropicCreditError as e:
                emit("error", {"step": "script_generation", "error": str(e)})
                raise
            except Exception as e:
                logger.error(f"Script generation failed: {e}")
                emit("error", {"step": "script_generation", "error": str(e)})
                raise ScriptGenerationError(f"Failed to generate script: {e}")

            # Step 3-8: Execute with retry loop
            for attempt in range(1, self.max_retries + 1):
                logger.info(f"Extraction attempt {attempt}/{self.max_retries}")
                
                # Execute script
                try:
                    extracted_json = self.script_runner.run(script.script_body, raw_text)
                    fields_found = len([f for f in extracted_json.values() if f is not None])
                    emit("script_executed", {
                        "attempt": attempt,
                        "fields_found": fields_found,
                        "fields_total": len(schema)
                    })
                    logger.info(f"Script executed, found {fields_found}/{len(schema)} fields")
                except Exception as e:
                    logger.error(f"Script execution failed: {e}")
                    extracted_json = {}
                    emit("error", {"step": "script_execution", "attempt": attempt, "error": str(e)})

                # dLLM validation
                try:
                    dllm_report = self.dllm_checker.check_fields(raw_text, extracted_json, schema)
                    emit("dllm_check_complete", {"report": dllm_report})
                    logger.info("dLLM validation complete")
                except MercuryCreditError as e:
                    logger.error(f"Mercury API credit error: {e}")
                    emit("error", {"step": "dllm_validation", "error": str(e)})
                    raise
                except Exception as e:
                    logger.error(f"dLLM validation failed: {e}")
                    dllm_report = {}
                    emit("error", {"step": "dllm_validation", "error": str(e)})

                # Analyze results
                missing_high_confidence = []
                missing_low_confidence = []

                if dllm_report and "fields" in dllm_report:
                    for field_name, field_info in dllm_report.get("fields", {}).items():
                        if field_info.get("status") in ["missing", "uncertain"]:
                            if field_info.get("confidence", 0) > self.confidence_threshold:
                                missing_high_confidence.append(field_name)
                            else:
                                missing_low_confidence.append(field_name)

                # Decide next action
                if not missing_high_confidence and not missing_low_confidence:
                    logger.info("All fields resolved successfully")
                    break
                elif missing_low_confidence and attempt < self.max_retries:
                    logger.info(f"Retrying with missing fields: {missing_low_confidence}")
                    emit("retry", {
                        "attempt": attempt,
                        "reason": "script_failure",
                        "fields": missing_low_confidence
                    })
                    
                    try:
                        script_before = script.script_body
                        script_after = self.llm_agent.revise_script(
                            script.script_body,
                            raw_text,
                            schema,
                            missing_low_confidence,
                            attempt
                        )
                        
                        script.script_body = script_after
                        script.version += 1
                        script.updated_at = datetime.utcnow()
                        self.db.commit()
                        logger.info(f"Script revised to v{script.version}")
                    except AnthropicCreditError as e:
                        emit("error", {"step": "script_revision", "error": str(e)})
                        raise
                    except Exception as e:
                        logger.error(f"Script revision failed: {e}")
                        emit("error", {"step": "script_revision", "error": str(e)})
                else:
                    missing_fields = missing_high_confidence + missing_low_confidence
                    logger.warning(f"Escalating {len(missing_fields)} fields to human")
                    break

            # Step 9: Save result
            final_status = StatusEnum.complete if not missing_fields else StatusEnum.partial
            
            result = ExtractionResult(
                filename=filename,
                fingerprint=fingerprint,
                script_version=script.version,
                raw_text=raw_text,
                extracted_json=extracted_json or {},
                human_overrides={},
                dllm_report=dllm_report or {},
                status=final_status
            )
            
            self.db.add(result)
            self.db.commit()
            self.db.refresh(result)
            logger.info(f"Result saved with ID {result.id}")

            if missing_fields:
                emit("escalated_to_human", {"fields": missing_fields, "result_id": result.id})
            else:
                emit("complete", {"result_id": result.id, "status": "success"})

            # Update script stats
            if script:
                if missing_fields:
                    script.fail_count += 1
                else:
                    script.success_count += 1
                self.db.commit()

            return result.id

        except (AnthropicCreditError, MercuryCreditError, APIError):
            raise
        except FingerprintError:
            raise
        except ScriptGenerationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected pipeline error: {e}")
            emit("error", {"step": "unknown", "error": str(e)})
            
            # Save failed result if we have partial data
            try:
                if fingerprint and script:
                    result = ExtractionResult(
                        filename=filename,
                        fingerprint=fingerprint or "unknown",
                        script_version=script.version if script else 1,
                        raw_text=raw_text,
                        extracted_json=extracted_json or {},
                        human_overrides={},
                        dllm_report=dllm_report or {},
                        status=StatusEnum.failed
                    )
                    self.db.add(result)
                    self.db.commit()
                    self.db.refresh(result)
                    logger.info(f"Failed result saved with ID {result.id}")
                    return result.id
            except Exception as save_error:
                logger.error(f"Failed to save error result: {save_error}")
            
            raise PipelineError(f"Extraction pipeline failed: {e}")

    def apply_human_overrides(self, result_id: int, overrides: Dict[str, Any]) -> Dict:
        """Apply human overrides to an extraction result."""
        result = self.db.query(ExtractionResult).filter_by(id=result_id).first()
        if not result:
            raise ValueError(f"Result {result_id} not found")

        for field_name, value in overrides.items():
            result.extracted_json[field_name] = value

        result.human_overrides = overrides
        result.status = StatusEnum.complete
        self.db.commit()

        return result.extracted_json
