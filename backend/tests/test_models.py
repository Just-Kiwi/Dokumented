"""
Tests for database models.
"""
import pytest
from datetime import datetime
from db.models import ScriptLibrary, ExtractionResult, RetryLog, AppConfig, StatusEnum, OutcomeEnum


class TestStatusEnum:
    """Tests for StatusEnum."""

    def test_status_enum_values(self):
        """Test StatusEnum has all expected values."""
        assert StatusEnum.complete.value == "complete"
        assert StatusEnum.partial.value == "partial"
        assert StatusEnum.failed.value == "failed"

    def test_status_enum_is_string_enum(self):
        """Test StatusEnum is a string enum."""
        assert issubclass(StatusEnum, str)


class TestOutcomeEnum:
    """Tests for OutcomeEnum."""

    def test_outcome_enum_values(self):
        """Test OutcomeEnum has all expected values."""
        assert OutcomeEnum.resolved.value == "resolved"
        assert OutcomeEnum.escalated.value == "escalated"
        assert OutcomeEnum.new_fingerprint.value == "new_fingerprint"

    def test_outcome_enum_is_string_enum(self):
        """Test OutcomeEnum is a string enum."""
        assert issubclass(OutcomeEnum, str)


class TestScriptLibraryModel:
    """Tests for ScriptLibrary model."""

    def test_create_script_library(self, test_db):
        """Test creating a ScriptLibrary record."""
        script = ScriptLibrary(
            fingerprint="invoice-standard",
            script_body="import re\nresult = {}",
            version=1
        )
        test_db.add(script)
        test_db.commit()
        
        retrieved = test_db.query(ScriptLibrary).filter_by(fingerprint="invoice-standard").first()
        assert retrieved is not None
        assert retrieved.fingerprint == "invoice-standard"
        assert retrieved.version == 1
        assert retrieved.success_count == 0
        assert retrieved.fail_count == 0

    def test_script_library_default_values(self, test_db):
        """Test ScriptLibrary has correct default values."""
        script = ScriptLibrary(
            fingerprint="test-format",
            script_body="result = {}"
        )
        test_db.add(script)
        test_db.commit()
        
        assert script.version == 1
        assert script.success_count == 0
        assert script.fail_count == 0

    def test_script_library_timestamps(self, test_db):
        """Test ScriptLibrary has timestamp fields."""
        script = ScriptLibrary(
            fingerprint="timestamp-test",
            script_body="result = {}"
        )
        test_db.add(script)
        test_db.commit()
        
        assert script.created_at is not None
        assert isinstance(script.created_at, datetime)

    def test_script_library_unique_fingerprint(self, test_db):
        """Test ScriptLibrary fingerprint must be unique."""
        script1 = ScriptLibrary(fingerprint="unique-test", script_body="result = {}")
        test_db.add(script1)
        test_db.commit()
        
        script2 = ScriptLibrary(fingerprint="unique-test", script_body="result = {}")
        test_db.add(script2)
        
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_script_library_version_increment(self, test_db, sample_script):
        """Test version increment functionality."""
        initial_version = sample_script.version
        sample_script.version += 1
        test_db.commit()
        
        assert sample_script.version == initial_version + 1

    def test_script_library_success_fail_counts(self, test_db, sample_script):
        """Test success and fail count tracking."""
        success_before = sample_script.success_count
        fail_before = sample_script.fail_count
        sample_script.success_count = success_before + 1
        sample_script.fail_count = fail_before + 1
        test_db.commit()
        
        assert sample_script.success_count == success_before + 1
        assert sample_script.fail_count == fail_before + 1


class TestExtractionResultModel:
    """Tests for ExtractionResult model."""

    def test_create_extraction_result(self, test_db, sample_script):
        """Test creating an ExtractionResult record."""
        result = ExtractionResult(
            filename="test_invoice.pdf",
            fingerprint=sample_script.fingerprint,
            script_version=1,
            raw_text="Raw text content",
            extracted_json={"invoice_number": "INV-001"},
            status=StatusEnum.complete
        )
        test_db.add(result)
        test_db.commit()
        
        retrieved = test_db.query(ExtractionResult).filter_by(filename="test_invoice.pdf").first()
        assert retrieved is not None
        assert retrieved.fingerprint == sample_script.fingerprint
        assert retrieved.extracted_json["invoice_number"] == "INV-001"

    def test_extraction_result_default_status(self, test_db, sample_script):
        """Test ExtractionResult has correct default status."""
        result = ExtractionResult(
            filename="default_status.pdf",
            fingerprint=sample_script.fingerprint,
            script_version=1,
            raw_text="text",
            extracted_json={}
        )
        test_db.add(result)
        test_db.commit()
        
        assert result.status == StatusEnum.complete

    def test_extraction_result_json_column(self, test_db, sample_script):
        """Test ExtractionResult JSON column works correctly."""
        complex_json = {
            "field1": "value1",
            "field2": 123,
            "nested": {"key": "value"},
            "list": [1, 2, 3]
        }
        result = ExtractionResult(
            filename="json_test.pdf",
            fingerprint=sample_script.fingerprint,
            script_version=1,
            raw_text="text",
            extracted_json=complex_json
        )
        test_db.add(result)
        test_db.commit()
        
        retrieved = test_db.query(ExtractionResult).filter_by(filename="json_test.pdf").first()
        assert retrieved.extracted_json == complex_json
        assert retrieved.extracted_json["nested"]["key"] == "value"

    def test_extraction_result_human_overrides(self, test_db, sample_script):
        """Test ExtractionResult human overrides column."""
        result = ExtractionResult(
            filename="with_overrides.pdf",
            fingerprint=sample_script.fingerprint,
            script_version=1,
            raw_text="text",
            extracted_json={"field1": "original"},
            human_overrides={"field1": "override_value"}
        )
        test_db.add(result)
        test_db.commit()
        
        assert result.human_overrides["field1"] == "override_value"

    def test_extraction_result_all_statuses(self, test_db, sample_script):
        """Test ExtractionResult with all status values."""
        for status in StatusEnum:
            result = ExtractionResult(
                filename=f"status_{status.value}.pdf",
                fingerprint=sample_script.fingerprint,
                script_version=1,
                raw_text="text",
                extracted_json={},
                status=status
            )
            test_db.add(result)
            test_db.commit()
            
            assert result.status == status


class TestRetryLogModel:
    """Tests for RetryLog model."""

    def test_create_retry_log(self, test_db, sample_extraction_result):
        """Test creating a RetryLog record."""
        retry_log = RetryLog(
            result_id=sample_extraction_result.id,
            attempt_number=1,
            missing_fields=["field1", "field2"],
            dllm_report={"fields": {"field1": {"status": "missing"}}},
            script_before="old script",
            script_after="new script",
            outcome=OutcomeEnum.resolved
        )
        test_db.add(retry_log)
        test_db.commit()
        
        assert retry_log.attempt_number == 1
        assert retry_log.outcome == OutcomeEnum.resolved

    def test_retry_log_json_columns(self, test_db, sample_extraction_result):
        """Test RetryLog JSON columns work correctly."""
        retry_log = RetryLog(
            result_id=sample_extraction_result.id,
            attempt_number=1,
            missing_fields=["a", "b", "c"],
            dllm_report={
                "fields": {
                    "a": {"status": "missing", "confidence": 0.9},
                    "b": {"status": "uncertain", "confidence": 0.5}
                }
            },
            script_before="before",
            outcome=OutcomeEnum.escalated
        )
        test_db.add(retry_log)
        test_db.commit()
        
        assert len(retry_log.missing_fields) == 3
        assert retry_log.dllm_report["fields"]["a"]["confidence"] == 0.9

    def test_retry_log_outcome_values(self, test_db, sample_extraction_result):
        """Test RetryLog with all outcome values."""
        for outcome in OutcomeEnum:
            retry_log = RetryLog(
                result_id=sample_extraction_result.id,
                attempt_number=1,
                missing_fields=[],
                dllm_report={},
                script_before="test",
                outcome=outcome
            )
            test_db.add(retry_log)
            test_db.commit()
            
            assert retry_log.outcome == outcome

    def test_retry_log_null_script_after(self, test_db, sample_extraction_result):
        """Test RetryLog with null script_after (for certain outcomes)."""
        retry_log = RetryLog(
            result_id=sample_extraction_result.id,
            attempt_number=1,
            missing_fields=[],
            dllm_report={},
            script_before="test",
            script_after=None,
            outcome=OutcomeEnum.escalated
        )
        test_db.add(retry_log)
        test_db.commit()
        
        assert retry_log.script_after is None


class TestAppConfigModel:
    """Tests for AppConfig model."""

    def test_create_app_config(self, test_db):
        """Test creating an AppConfig record."""
        config = AppConfig(
            key="TEST_KEY",
            value="test_value"
        )
        test_db.add(config)
        test_db.commit()
        
        retrieved = test_db.query(AppConfig).filter_by(key="TEST_KEY").first()
        assert retrieved is not None
        assert retrieved.value == "test_value"

    def test_app_config_unique_key(self, test_db):
        """Test AppConfig key must be unique."""
        config1 = AppConfig(key="UNIQUE_KEY", value="value1")
        test_db.add(config1)
        test_db.commit()
        
        config2 = AppConfig(key="UNIQUE_KEY", value="value2")
        test_db.add(config2)
        
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_app_config_timestamps(self, test_db):
        """Test AppConfig has timestamp fields."""
        config = AppConfig(key="TIMESTAMP_KEY", value="value")
        test_db.add(config)
        test_db.commit()
        
        assert config.created_at is not None
        assert config.updated_at is not None
        assert isinstance(config.created_at, datetime)

    def test_app_config_multiple_keys(self, test_db):
        """Test creating multiple AppConfig records."""
        configs = [
            AppConfig(key="KEY1", value="value1"),
            AppConfig(key="KEY2", value="value2"),
            AppConfig(key="KEY3", value="value3"),
        ]
        for config in configs:
            test_db.add(config)
        test_db.commit()
        
        all_configs = test_db.query(AppConfig).all()
        assert len(all_configs) == 3


class TestModelRelationships:
    """Tests for model relationships."""

    def test_script_library_relationship(self, test_db, sample_script, sample_extraction_result):
        """Test ScriptLibrary relationship with ExtractionResult."""
        assert sample_extraction_result.script == sample_script
        assert sample_extraction_result in sample_script.extraction_results

    def test_extraction_result_relationship(self, test_db, sample_extraction_result, sample_script):
        """Test ExtractionResult relationship with ScriptLibrary."""
        assert sample_extraction_result.fingerprint == sample_script.fingerprint
        assert sample_extraction_result.script.fingerprint == sample_script.fingerprint
