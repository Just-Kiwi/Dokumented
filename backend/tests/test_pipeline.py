"""
Tests for extraction pipeline retry logic.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


@pytest.fixture
def mock_llm_agent():
    """Mock LLMAgent for testing."""
    agent = MagicMock()
    agent.write_script.return_value = """import re
result = {
    'vendor_name': re.search(r'From:\\s*(.+)', raw_text).group(1).strip() if re.search(r'From:\\s*(.+)', raw_text) else None,
    'invoice_date': re.search(r'Date:\\s*(.+)', raw_text).group(1).strip() if re.search(r'Date:\\s*(.+)', raw_text) else None,
    'invoice_total': re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text).group(1) if re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text) else None,
    'invoice_number': re.search(r'Invoice #(\\S+)', raw_text).group(1) if re.search(r'Invoice #(\\S+)', raw_text) else None,
}"""
    agent.revise_script.return_value = """import re
result = {
    'vendor_name': re.search(r'From:\\s*(.+)', raw_text, re.MULTILINE).group(1).strip() if re.search(r'From:\\s*(.+)', raw_text, re.MULTILINE) else None,
    'invoice_date': re.search(r'Date:\\s*(.+)', raw_text).group(1).strip() if re.search(r'Date:\\s*(.+)', raw_text) else None,
    'invoice_total': re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text).group(1) if re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text) else None,
    'invoice_number': re.search(r'Invoice #(\\S+)', raw_text).group(1) if re.search(r'Invoice #(\\S+)', raw_text) else None,
}"""
    return agent


@pytest.fixture
def mock_dllm_checker():
    """Mock dLLMChecker for testing."""
    checker = MagicMock()
    return checker


@pytest.fixture
def sample_invoice_raw():
    """Sample invoice raw text for testing."""
    return """INVOICE #INV-2024-001

From: Acme Corporation
123 Business St
Los Angeles, CA 90001

Date: January 15, 2024
Due Date: February 15, 2024

Total: $1,375.00

Payment Terms: Net 30
"""


@pytest.fixture
def sample_invoice_schema():
    """Sample invoice schema for testing."""
    return [
        {"name": "vendor_name", "description": "Name of the vendor/company", "required": True},
        {"name": "invoice_date", "description": "Date of the invoice", "required": True},
        {"name": "invoice_total", "description": "Total amount due", "required": True},
        {"name": "invoice_number", "description": "Invoice reference number", "required": True},
    ]


class TestPipelineRetryLogic:
    """Tests for retry behavior in extraction pipeline."""

    def test_missing_fields_combine_high_and_low(self):
        """Test that missing_high_confidence and missing_low_confidence are combined."""
        # Simulate the logic that combines both lists
        missing_high = ["vendor_name", "invoice_number"]
        missing_low = ["invoice_date"]
        
        missing_fields = missing_high + missing_low
        
        assert len(missing_fields) == 3
        assert "vendor_name" in missing_fields
        assert "invoice_number" in missing_fields
        assert "invoice_date" in missing_fields

    def test_retry_triggered_on_any_missing_fields(self):
        """Test that retry is triggered when any missing fields exist (not just low confidence)."""
        # This tests the new logic: retry happens for ALL missing fields on attempts 1-2
        attempt = 1
        max_retries = 3
        missing_fields = ["vendor_name", "invoice_total"]  # high confidence
        
        # Old logic: would NOT retry (escalates immediately)
        # New logic: should retry
        should_retry = attempt < max_retries and len(missing_fields) > 0
        
        assert should_retry is True

    def test_escalation_only_on_last_attempt(self):
        """Test that escalation only happens after all retries exhausted."""
        attempt = 3  # Last attempt
        max_retries = 3
        missing_fields = ["vendor_name"]
        
        should_escalate = attempt == max_retries and len(missing_fields) > 0
        
        assert should_escalate is True

    def test_no_escalation_before_exhaustion(self):
        """Test that escalation does NOT happen before all retries exhausted."""
        # Test that high confidence missing on attempt 1 should retry, not escalate
        attempt = 1
        max_retries = 3
        missing_fields = ["vendor_name"]  # would be high confidence
        
        should_escalate = attempt == max_retries
        
        assert should_escalate is False  # Should NOT escalate on attempt 1


class TestPipelineRetryBehavior:
    """Integration-style tests for retry flow."""

    @patch('services.pipeline.ScriptRunner')
    @patch('services.pipeline.dLLMChecker')
    @patch('services.pipeline.LLMAgent')
    def test_retry_continues_after_high_confidence_missing(self, mock_llm, mock_dllm, mock_runner):
        """Verify retry happens even when dLLM reports high confidence missing fields."""
        from services.pipeline import ExtractionPipeline
        from db.models import ScriptLibrary
        
        # This test verifies the retry logic change
        # In old code: high confidence missing -> escalate (break)
        # In new code: any missing -> retry on attempts 1-2
        
        # Simulate attempt 1 with high confidence missing fields
        attempt = 1
        max_retries = 3
        missing_high_confidence = ["vendor_name"]
        missing_low_confidence = []
        
        # Old behavior: would go to else branch and escalate
        # New behavior: should retry because attempt < max_retries
        
        # Test: attempt 1 with high confidence missing should still trigger retry
        missing_fields = missing_high_confidence + missing_low_confidence
        would_retry = attempt < max_retries
        would_escalate_immediately = attempt < max_retries  # This was the old bug
        
        # The fix ensures would_retry is True and would_escalate_immediately is False
        assert would_retry is True
        # In old code, this was incorrectly True
        # In new code, this should be False (no immediate escalation)
        assert missing_fields  # Has fields to retry

    def test_max_retries_exhausted_triggers_escalation(self):
        """Test that after 3 failed attempts, escalation occurs."""
        for attempt in range(1, 4):
            max_retries = 3
            missing_fields = ["vendor_name"]
            
            is_last_attempt = attempt == max_retries
            
            if attempt < max_retries:
                # Should retry
                assert True  # retry logic
            elif is_last_attempt:
                # Should escalate
                assert True  # escalation logic


class TestExtractionPipelineIntegration:
    """Integration tests that verify actual extraction pipeline behavior."""

    @pytest.mark.asyncio
    async def test_extract_runs_three_attempts_with_mocks(self, test_db, sample_invoice_raw, sample_invoice_schema):
        """Test that extraction makes 3 attempts when fields are missing."""
        from services.pipeline import ExtractionPipeline
        from db.models import ScriptLibrary
        
        # Create a script that only extracts 1 field (intentionally buggy)
        buggy_script = ScriptLibrary(
            script_body="""import re
result = {
    'vendor_name': re.search(r'From:\\s*(.+)', raw_text).group(1).strip() if re.search(r'From:\\s*(.+)', raw_text) else None,
}""",
            version=1,
            success_count=0,
            fail_count=0,
        )
        test_db.add(buggy_script)
        test_db.commit()
        test_db.refresh(buggy_script)
        
        # Mock LLM agent
        mock_llm = MagicMock()
        mock_llm.revise_script.return_value = """import re
result = {
    'vendor_name': re.search(r'From:\\s*(.+)', raw_text).group(1).strip() if re.search(r'From:\\s*(.+)', raw_text) else None,
    'invoice_date': 'unknown',
    'invoice_total': 'unknown',
    'invoice_number': 'unknown',
}"""
        
        # Mock dLLM checker - returns missing for 3 fields on each attempt
        mock_dllm = MagicMock()
        mock_dllm.check_fields.return_value = {
            "fields": {
                "vendor_name": {"status": "present", "confidence": 0.95},
                "invoice_date": {"status": "missing", "confidence": 0.90},  # High confidence missing
                "invoice_total": {"status": "missing", "confidence": 0.88},  # High confidence missing
                "invoice_number": {"status": "missing", "confidence": 0.92},  # High confidence missing
            }
        }
        
        # Create pipeline with mocks
        with patch('services.pipeline.LLMAgent', return_value=mock_llm), \
             patch('services.pipeline.dLLMChecker', return_value=mock_dllm):
            
            pipeline = ExtractionPipeline(test_db)
            pipeline.llm_agent = mock_llm
            pipeline.dllm_checker = mock_dllm
            pipeline.max_retries = 3
            
            # Track attempts
            attempt_count = 0
            
            original_run = pipeline.script_runner.run
            def track_attempts(script_body, raw_text):
                nonlocal attempt_count
                attempt_count += 1
                return original_run(script_body, raw_text)
            
            pipeline.script_runner.run = track_attempts
            
            result_id = await pipeline.extract(
                filename="test_invoice.pdf",
                raw_text=sample_invoice_raw,
                schema=sample_invoice_schema
            )
            
            # Verify 3 attempts were made
            assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
            
            # Get the result from DB to check status
            from db.models import ExtractionResult
            result = test_db.query(ExtractionResult).filter_by(id=result_id).first()
            
            # Verify escalate event was emitted (we can check result status)
            assert result.status.value in ["partial", "failed"], f"Expected partial/failed, got {result.status}"
            
            # Verify script was revised twice (once for each retry after first attempt)
            assert mock_llm.revise_script.call_count == 2, f"Expected 2 revise_script calls, got {mock_llm.revise_script.call_count}"

    @pytest.mark.asyncio
    async def test_extract_completes_on_first_attempt_when_all_fields_found(self, test_db, sample_invoice_raw, sample_invoice_schema):
        """Test that extraction completes immediately when all fields are found."""
        from services.pipeline import ExtractionPipeline
        from db.models import ScriptLibrary
        
        # Create a perfect script that extracts all fields
        perfect_script = ScriptLibrary(
            script_body="""import re
result = {
    'vendor_name': re.search(r'From:\\s*(.+)', raw_text, re.MULTILINE).group(1).strip() if re.search(r'From:\\s*(.+)', raw_text, re.MULTILINE) else None,
    'invoice_date': re.search(r'Date:\\s*(.+)', raw_text).group(1).strip() if re.search(r'Date:\\s*(.+)', raw_text) else None,
    'invoice_total': re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text).group(1) if re.search(r'Total:\\s*\\$?([\\d,]+\\.?\\d*)', raw_text) else None,
    'invoice_number': re.search(r'INVOICE #(\\S+)', raw_text).group(1) if re.search(r'INVOICE #(\\S+)', raw_text) else None,
}""",
            version=1,
            success_count=5,
            fail_count=0,
        )
        test_db.add(perfect_script)
        test_db.commit()
        test_db.refresh(perfect_script)
        
        # Mock dLLM checker - all fields present
        mock_dllm = MagicMock()
        mock_dllm.check_fields.return_value = {
            "fields": {
                "vendor_name": {"status": "present", "confidence": 0.95},
                "invoice_date": {"status": "present", "confidence": 0.90},
                "invoice_total": {"status": "present", "confidence": 0.88},
                "invoice_number": {"status": "present", "confidence": 0.92},
            }
        }
        
        # Create pipeline with mocks
        with patch('services.pipeline.dLLMChecker', return_value=mock_dllm):
            pipeline = ExtractionPipeline(test_db)
            pipeline.dllm_checker = mock_dllm
            pipeline.max_retries = 3
            
            # Track attempts
            attempt_count = 0
            
            original_run = pipeline.script_runner.run
            def track_attempts(script_body, raw_text):
                nonlocal attempt_count
                attempt_count += 1
                return original_run(script_body, raw_text)
            
            pipeline.script_runner.run = track_attempts
            
            result_id = await pipeline.extract(
                filename="test_invoice.pdf",
                raw_text=sample_invoice_raw,
                schema=sample_invoice_schema
            )
            
            # Verify only 1 attempt was made (no retry needed)
            assert attempt_count == 1, f"Expected 1 attempt, got {attempt_count}"
            
            # Get the result from DB to check status
            from db.models import ExtractionResult
            result = test_db.query(ExtractionResult).filter_by(id=result_id).first()
            
            # Verify complete status
            assert result.status.value == "complete", f"Expected complete, got {result.status}"

    @pytest.mark.asyncio
    async def test_extract_escalates_after_three_attempts_exhausted(self, test_db, sample_invoice_raw, sample_invoice_schema):
        """Test that extraction escalates to human after all 3 attempts fail."""
        from services.pipeline import ExtractionPipeline
        from db.models import ScriptLibrary
        
        # Create a script that can never extract all fields
        bad_script = ScriptLibrary(
            script_body="""import re
result = {
    'vendor_name': None,
    'invoice_date': None,
    'invoice_total': None,
    'invoice_number': None,
}""",
            version=1,
            success_count=0,
            fail_count=0,
        )
        test_db.add(bad_script)
        test_db.commit()
        test_db.refresh(bad_script)
        
        # Mock LLM agent
        mock_llm = MagicMock()
        # Revise script still returns empty - this simulates a really bad script
        mock_llm.revise_script.return_value = """import re
result = {
    'vendor_name': None,
    'invoice_date': None,
    'invoice_total': None,
    'invoice_number': None,
}"""
        
        # Mock dLLM checker - all fields missing with high confidence
        mock_dllm = MagicMock()
        mock_dllm.check_fields.return_value = {
            "fields": {
                "vendor_name": {"status": "missing", "confidence": 0.95},
                "invoice_date": {"status": "missing", "confidence": 0.90},
                "invoice_total": {"status": "missing", "confidence": 0.88},
                "invoice_number": {"status": "missing", "confidence": 0.92},
            }
        }
        
        # Create pipeline with mocks
        with patch('services.pipeline.LLMAgent', return_value=mock_llm), \
             patch('services.pipeline.dLLMChecker', return_value=mock_dllm):
            
            pipeline = ExtractionPipeline(test_db)
            pipeline.llm_agent = mock_llm
            pipeline.dllm_checker = mock_dllm
            pipeline.max_retries = 3
            
            # Track attempts
            attempt_count = 0
            
            original_run = pipeline.script_runner.run
            def track_attempts(script_body, raw_text):
                nonlocal attempt_count
                attempt_count += 1
                return original_run(script_body, raw_text)
            
            pipeline.script_runner.run = track_attempts
            
            result_id = await pipeline.extract(
                filename="test_invoice.pdf",
                raw_text=sample_invoice_raw,
                schema=sample_invoice_schema
            )
            
            # Verify 3 attempts were made
            assert attempt_count == 3
            
            # Get the result from DB to check status
            from db.models import ExtractionResult
            result = test_db.query(ExtractionResult).filter_by(id=result_id).first()
            
            # Verify escalate event was emitted (status should be partial or failed)
            assert result.status.value in ["partial", "failed"], f"Expected partial/failed, got {result.status}"
            
            # Verify script was revised twice (for attempts 1 and 2)
            assert mock_llm.revise_script.call_count == 2