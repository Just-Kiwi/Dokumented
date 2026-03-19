"""
Main extraction pipeline orchestrating all components.
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from sqlalchemy.orm import Session
from db.models import ScriptLibrary, ExtractionResult, RetryLog, StatusEnum, OutcomeEnum
from agents.llm_agent import LLMAgent
from agents.dllm_checker import dLLMChecker
from services.script_runner import ScriptRunner
from parsers.doc_parser import DocumentParser
import json
from datetime import datetime


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
        """
        
        def emit(event: str, data: Dict = None):
            """Emit WebSocket event."""
            if events_callback:
                events_callback({"event": event, "data": data or {}})

        # Step 1: Fingerprint
        fingerprint = self.llm_agent.fingerprint(raw_text)
        emit("fingerprint_assigned", {"fingerprint": fingerprint})

        # Step 2: Script lookup or creation
        script = self.db.query(ScriptLibrary).filter_by(fingerprint=fingerprint).first()
        
        if script:
            emit("script_found", {"version": script.version})
        else:
            # Write new script
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

        # Step 3-8: Execute with retry loop
        extracted_json = None
        attempt = 0
        missing_fields = []

        for attempt in range(1, self.max_retries + 1):
            # Execute script
            extracted_json = self.script_runner.run(script.script_body, raw_text)
            emit("script_executed", {
                "attempt": attempt,
                "fields_found": len([f for f in extracted_json.values() if f is not None]),
                "fields_total": len(schema)
            })

            # dLLM validation
            dllm_report = self.dllm_checker.check_fields(raw_text, extracted_json, schema)
            emit("dllm_check_complete", {"report": dllm_report})

            # Analyze results
            missing_high_confidence = []
            missing_low_confidence = []

            for field_name, field_info in dllm_report.get("fields", {}).items():
                if field_info["status"] in ["missing", "uncertain"]:
                    if field_info["confidence"] > self.confidence_threshold:
                        missing_high_confidence.append(field_name)
                    else:
                        missing_low_confidence.append(field_name)

            # Decide next action
            if not missing_high_confidence and not missing_low_confidence:
                # All fields resolved
                break
            elif missing_low_confidence and attempt < self.max_retries:
                # Script likely failed, retry
                emit("retry", {
                    "attempt": attempt,
                    "reason": "script_failure",
                    "fields": missing_low_confidence
                })
                
                # LLM revision
                script_before = script.script_body
                script_after = self.llm_agent.revise_script(
                    script.script_body,
                    raw_text,
                    schema,
                    missing_low_confidence,
                    attempt
                )
                
                # Log retry
                retry_log = RetryLog(
                    result_id=None,  # Set after result creation
                    attempt_number=attempt,
                    missing_fields=missing_low_confidence,
                    dllm_report=dllm_report,
                    script_before=script_before,
                    script_after=script_after,
                    outcome=OutcomeEnum.resolved
                )
                # Don't add yet, we need result_id
                
                # Update script
                script.script_body = script_after
                script.version += 1
                script.updated_at = datetime.utcnow()
                self.db.commit()
            else:
                # Escalate to human or new fingerprint attempt
                missing_fields = missing_high_confidence + missing_low_confidence
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
            status=final_status
        )
        
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)

        # Update any retry logs with result_id
        # (In a real system, you'd track retry_logs during the loop)

        if missing_fields:
            emit("escalated_to_human", {"fields": missing_fields, "result_id": result.id})
        else:
            emit("complete", {"result_id": result.id, "status": "success"})

        # Update script stats
        if missing_fields:
            script.fail_count += 1
        else:
            script.success_count += 1
        self.db.commit()

        return result.id

    def apply_human_overrides(self, result_id: int, overrides: Dict[str, Any]) -> Dict:
        """Apply human overrides to an extraction result."""
        result = self.db.query(ExtractionResult).filter_by(id=result_id).first()
        if not result:
            raise ValueError(f"Result {result_id} not found")

        # Merge overrides into extracted JSON
        for field_name, value in overrides.items():
            result.extracted_json[field_name] = value

        # Record overrides
        result.human_overrides = overrides
        result.status = StatusEnum.complete
        self.db.commit()

        return result.extracted_json
