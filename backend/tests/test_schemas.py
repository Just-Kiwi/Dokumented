"""
Tests for Pydantic schemas - request/response model validation.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError
from models.schemas import (
    ConfigUpdate, ConfigResponse, FieldDefinition, SchemaRequest,
    ExtractRequest, FieldStatus, dLLMReport, ExtractionReportResponse,
    HumanOverride, HumanOverridesRequest, WSEvent
)


class TestConfigSchemas:
    """Tests for configuration schemas."""

    def test_config_update_valid(self):
        """Test valid ConfigUpdate creation."""
        config = ConfigUpdate(key="ANTHROPIC_API_KEY", value="sk-ant-test-key")
        assert config.key == "ANTHROPIC_API_KEY"
        assert config.value == "sk-ant-test-key"

    def test_config_update_missing_key(self):
        """Test ConfigUpdate requires key."""
        with pytest.raises(ValidationError):
            ConfigUpdate(value="some-value")

    def test_config_update_missing_value(self):
        """Test ConfigUpdate requires value."""
        with pytest.raises(ValidationError):
            ConfigUpdate(key="SOME_KEY")

    def test_config_response_valid(self):
        """Test valid ConfigResponse creation."""
        response = ConfigResponse(
            key="MERCURY_API_KEY",
            value="test-value",
            updated_at=datetime.utcnow()
        )
        assert response.key == "MERCURY_API_KEY"
        assert response.value == "test-value"
        assert isinstance(response.updated_at, datetime)


class TestFieldSchemas:
    """Tests for field definition schemas."""

    def test_field_definition_valid(self):
        """Test valid FieldDefinition creation."""
        field = FieldDefinition(
            name="invoice_number",
            description="The invoice number",
            required=True
        )
        assert field.name == "invoice_number"
        assert field.description == "The invoice number"
        assert field.required is True

    def test_field_definition_defaults(self):
        """Test FieldDefinition has correct defaults."""
        field = FieldDefinition(name="simple_field")
        assert field.description is None
        assert field.required is True

    def test_field_definition_optional(self):
        """Test FieldDefinition with optional=False."""
        field = FieldDefinition(name="optional_field", required=False)
        assert field.required is False

    def test_field_definition_missing_name(self):
        """Test FieldDefinition requires name."""
        with pytest.raises(ValidationError):
            FieldDefinition(description="Some description")


class TestSchemaRequest:
    """Tests for SchemaRequest schema."""

    def test_schema_request_valid(self):
        """Test valid SchemaRequest creation."""
        request = SchemaRequest(fields=[
            FieldDefinition(name="field1", description="First field"),
            FieldDefinition(name="field2", required=False),
        ])
        assert len(request.fields) == 2
        assert request.fields[0].name == "field1"

    def test_schema_request_empty_fields(self):
        """Test SchemaRequest with empty fields list."""
        request = SchemaRequest(fields=[])
        assert request.fields == []

    def test_schema_request_requires_fields(self):
        """Test SchemaRequest requires fields."""
        with pytest.raises(ValidationError):
            SchemaRequest()


class TestExtractRequest:
    """Tests for ExtractRequest schema."""

    def test_extract_request_valid(self):
        """Test valid ExtractRequest creation."""
        request = ExtractRequest(
            filename="invoice.pdf",
            raw_text="Invoice content here",
            schema=[
                {"name": "amount", "description": "Total amount"}
            ]
        )
        assert request.filename == "invoice.pdf"
        assert request.raw_text == "Invoice content here"
        assert len(request.schema) == 1

    def test_extract_request_without_schema(self):
        """Test ExtractRequest without schema (optional)."""
        request = ExtractRequest(
            filename="document.txt",
            raw_text="Some text"
        )
        assert request.schema is None

    def test_extract_request_missing_filename(self):
        """Test ExtractRequest requires filename."""
        with pytest.raises(ValidationError):
            ExtractRequest(raw_text="Some text")

    def test_extract_request_missing_raw_text(self):
        """Test ExtractRequest requires raw_text."""
        with pytest.raises(ValidationError):
            ExtractRequest(filename="test.pdf")


class TestFieldStatus:
    """Tests for FieldStatus schema."""

    def test_field_status_filled(self):
        """Test FieldStatus with filled status."""
        status = FieldStatus(
            status="filled",
            value="123.45",
            confidence=0.95
        )
        assert status.status == "filled"
        assert status.value == "123.45"
        assert status.confidence == 0.95

    def test_field_status_missing(self):
        """Test FieldStatus with missing status."""
        status = FieldStatus(
            status="missing",
            value=None,
            confidence=0.85
        )
        assert status.status == "missing"
        assert status.value is None

    def test_field_status_uncertain(self):
        """Test FieldStatus with uncertain status."""
        status = FieldStatus(
            status="uncertain",
            value="maybe",
            confidence=0.5
        )
        assert status.status == "uncertain"

    def test_field_status_requires_status(self):
        """Test FieldStatus requires status field."""
        with pytest.raises(ValidationError):
            FieldStatus(value="test", confidence=0.9)

    def test_field_status_requires_confidence(self):
        """Test FieldStatus requires confidence field."""
        with pytest.raises(ValidationError):
            FieldStatus(status="filled", value="test")


class TestDLLMReport:
    """Tests for dLLMReport schema."""

    def test_dllm_report_valid(self):
        """Test valid dLLMReport creation."""
        report = dLLMReport(fields={
            "invoice_number": FieldStatus(status="filled", value="INV-001", confidence=0.99),
            "amount": FieldStatus(status="missing", value=None, confidence=0.9),
        })
        assert len(report.fields) == 2
        assert report.fields["invoice_number"].status == "filled"

    def test_dllm_report_empty_fields(self):
        """Test dLLMReport with empty fields."""
        report = dLLMReport(fields={})
        assert report.fields == {}


class TestExtractionReportResponse:
    """Tests for ExtractionReportResponse schema."""

    def test_extraction_report_response_valid(self):
        """Test valid ExtractionReportResponse creation."""
        response = ExtractionReportResponse(
            result_id=1,
            filename="invoice.pdf",
            fingerprint="vendor-invoice",
            status="complete",
            extracted_json={"amount": "100.00"},
            missing_fields=[]
        )
        assert response.result_id == 1
        assert response.filename == "invoice.pdf"
        assert response.fingerprint == "vendor-invoice"

    def test_extraction_report_response_with_missing_fields(self):
        """Test ExtractionReportResponse with missing fields."""
        response = ExtractionReportResponse(
            result_id=2,
            filename="receipt.txt",
            fingerprint="receipt-simple",
            status="partial",
            extracted_json={"vendor": "Store"},
            missing_fields=["amount", "date"]
        )
        assert len(response.missing_fields) == 2
        assert "amount" in response.missing_fields

    def test_extraction_report_response_with_dllm_report(self):
        """Test ExtractionReportResponse with dLLM report."""
        response = ExtractionReportResponse(
            result_id=3,
            filename="doc.pdf",
            fingerprint="form-standard",
            status="complete",
            extracted_json={},
            missing_fields=[],
            dllm_report={"confidence": 0.85}
        )
        assert response.dllm_report is not None


class TestHumanOverride:
    """Tests for HumanOverride schema."""

    def test_human_override_valid(self):
        """Test valid HumanOverride creation."""
        override = HumanOverride(field_name="amount", value="500.00")
        assert override.field_name == "amount"
        assert override.value == "500.00"

    def test_human_override_null_value(self):
        """Test HumanOverride with null value (missing field)."""
        override = HumanOverride(field_name="missing_field", value=None)
        assert override.field_name == "missing_field"
        assert override.value is None

    def test_human_override_requires_field_name(self):
        """Test HumanOverride requires field_name."""
        with pytest.raises(ValidationError):
            HumanOverride(value="some-value")


class TestHumanOverridesRequest:
    """Tests for HumanOverridesRequest schema."""

    def test_human_overrides_request_valid(self):
        """Test valid HumanOverridesRequest creation."""
        request = HumanOverridesRequest(
            result_id=1,
            overrides=[
                HumanOverride(field_name="field1", value="value1"),
                HumanOverride(field_name="field2", value=None),
            ]
        )
        assert request.result_id == 1
        assert len(request.overrides) == 2

    def test_human_overrides_request_empty_overrides(self):
        """Test HumanOverridesRequest with empty overrides."""
        request = HumanOverridesRequest(result_id=1, overrides=[])
        assert request.overrides == []


class TestWSEvent:
    """Tests for WebSocket event schema."""

    def test_ws_event_valid(self):
        """Test valid WSEvent creation."""
        event = WSEvent(
            event="complete",
            data={"result_id": 1, "status": "success"}
        )
        assert event.event == "complete"
        assert event.data["result_id"] == 1

    def test_ws_event_without_data(self):
        """Test WSEvent without data (optional)."""
        event = WSEvent(event="ping")
        assert event.event == "ping"
        assert event.data is None

    def test_ws_event_requires_event(self):
        """Test WSEvent requires event field."""
        with pytest.raises(ValidationError):
            WSEvent(data={"key": "value"})
