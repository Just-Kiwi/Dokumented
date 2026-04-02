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

    def get_best_script(self):
        """Get the script with the highest success count."""
        script = self.db.query(ScriptLibrary).order_by(ScriptLibrary.success_count.desc()).first()
        logger.info(f"[DEBUG get_best_script] Found: {script}")
        return script

    def create_new_script(self, raw_text: str, schema: List[Dict]) -> ScriptLibrary:
        """Create a new extraction script using LLM."""
        logger.info(f"[DEBUG create_new_script] schema={schema}")
        script_body = self.llm_agent.write_script(raw_text, schema)
        logger.info(f"[DEBUG create_new_script] Generated script body: {script_body[:200]}...")
        script = ScriptLibrary(
            script_body=script_body,
            version=1
        )
        self.db.add(script)
        self.db.commit()
        self.db.refresh(script)
        logger.info(f"[DEBUG create_new_script] Script saved to DB with id={script.id}")
        return script
    
    def fix_script_syntax(self, script_body: str, error: SyntaxError) -> str:
        """Attempt to fix common syntax errors in generated scripts."""
        import re
        
        fixed = script_body
        
        # Fix unterminated strings - add closing quote
        if "unterminated string literal" in str(error):
            lines = fixed.split('\n')
            for i, line in enumerate(lines):
                quote_count = line.count("'") - line.count("\\'")
                if quote_count % 2 != 0:
                    lines[i] = line + "'"
            fixed = '\n'.join(lines)
        
        # Fix missing colons after if/for/while/def
        for keyword in ['if ', 'for ', 'while ', 'def ']:
            pattern = keyword + r'([^\n:]+)\n'
            replacement = keyword + r'\1:\n'
            fixed = re.sub(pattern, replacement, fixed)
        
        # Fix missing closing brackets
        open_parens = fixed.count('(') - fixed.count(')')
        open_brackets = fixed.count('[') - fixed.count(']')
        open_braces = fixed.count('{') - fixed.count('}')
        
        fixed = fixed + ')' * max(0, open_parens)
        fixed = fixed + ']' * max(0, open_brackets)
        fixed = fixed + '}' * max(0, open_braces)
        
        logger.info(f"Attempted to fix script syntax, result: {fixed[:200]}...")
        return fixed

    async def extract(self, filename: str, raw_text: str, schema: List[Dict],
                     events_callback=None) -> int:
        """
        Full extraction pipeline. Returns the extraction_result id.
        
        Events emitted:
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

        script = None
        extracted_json = {}
        dllm_report = {}
        missing_fields = []
        
        try:
            # Step 1: Get best script or create new
            logger.info(f"Starting extraction for {filename}")
            logger.info(f"[DEBUG extract] schema length: {len(schema)}")
            
            # Fallback to default schema if empty
            if not schema:
                logger.warning("Empty schema in extract(), using default fields")
                schema = [
                    {"name": "vendor_name", "description": "Name of vendor", "required": True},
                    {"name": "invoice_date", "description": "Invoice date", "required": True},
                    {"name": "invoice_total", "description": "Total amount", "required": True},
                    {"name": "invoice_number", "description": "Invoice number", "required": True}
                ]
                logger.info(f"[DEBUG extract] Using default schema with {len(schema)} fields")
            
            script = self.get_best_script()
            
            if script:
                emit("script_found", {"version": script.version})
                logger.info(f"Found existing script v{script.version} (success_count={script.success_count})")
            else:
                logger.info("[DEBUG extract] No existing script, creating new one")
                script = self.create_new_script(raw_text, schema)
                emit("script_written", {"version": script.version})
                logger.info(f"Created new script v{script.version}")

            # Step 2-7: Execute with retry loop
            for attempt in range(1, self.max_retries + 1):
                logger.info(f"Extraction attempt {attempt}/{self.max_retries}")
                
                # Validate script before execution
                try:
                    import ast
                    ast.parse(script.script_body)
                    logger.info("Script syntax validated successfully")
                except SyntaxError as se:
                    logger.error(f"Script has syntax error: {se}")
                    script.script_body = self.fix_script_syntax(script.script_body, se)
                    try:
                        ast.parse(script.script_body)
                        logger.info("Script syntax fixed and validated")
                    except SyntaxError as se2:
                        logger.error(f"Could not fix script syntax: {se2}")
                        emit("error", {"step": "script_validation", "attempt": attempt, "error": str(se2)})
                        continue
                
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
                    
                    # If this was the last attempt and we still have missing fields, generate new script
                    if attempt == self.max_retries and missing_fields:
                        logger.warning(f"All {self.max_retries} attempts failed. Generating new script...")
                        emit("retry_exhausted", {"attempts": self.max_retries, "fields": missing_fields})
                        
                        script = self.create_new_script(raw_text, schema)
                        logger.info(f"Generated new script v{script.version} to replace failed one")
                        
                        # Reset for next extraction cycle - this will be saved as failed result
                        # The new script will be tried next time a similar document comes in
                        break
                    
                    logger.warning(f"Escalating {len(missing_fields)} fields to human")
                    break

            # Step 8: Save result
            final_status = StatusEnum.complete if not missing_fields else StatusEnum.partial
            
            result = ExtractionResult(
                filename=filename,
                script_id=script.id if script else None,
                script_version=script.version if script else 1,
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
            logger.error(f">>> API Error caught: {type(e).__name__}: {e}")
            raise
        except ScriptGenerationError:
            logger.error(f">>> ScriptGenerationError caught: {e}")
            raise
        except Exception as e:
            logger.error(f">>> Unexpected pipeline error: {type(e).__name__}: {e}")
            import traceback
            logger.error(f">>> Traceback: {traceback.format_exc()}")
            emit("error", {"step": "unknown", "error": str(e)})
            
            # Save failed result if we have partial data
            try:
                if script:
                    result = ExtractionResult(
                        filename=filename,
                        script_id=script.id if script else None,
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
