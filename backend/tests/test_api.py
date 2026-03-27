"""
Tests for API endpoints using direct function calls instead of TestClient.
"""
import pytest
from db.models import ScriptLibrary, ExtractionResult, StatusEnum
from main import health_check, list_config, get_config_by_key, get_script, list_scripts, get_extraction
from fastapi import HTTPException
from config import get_config, mask_api_key


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health check returns OK."""
        response = health_check()
        assert response["status"] == "ok"
        assert response["service"] == "Dokumented API"


class TestConfigEndpoints:
    """Tests for configuration endpoints from .env."""

    def test_list_config_returns_all_keys(self):
        """Test listing all configurations from .env."""
        result = list_config()
        assert "OPENROUTER_API_KEY" in result
        assert "OPENROUTER_BASE_URL" in result
        assert "MAX_RETRIES" in result
        assert "CONFIDENCE_THRESHOLD" in result

    def test_list_config_shows_source(self):
        """Test that config shows source as 'environment'."""
        result = list_config()
        for key in result:
            assert result[key]["source"] == "environment"

    def test_list_config_api_keys_masked(self):
        """Test that API keys are masked for security."""
        result = list_config()
        openrouter = result.get("OPENROUTER_API_KEY", {})
        
        if openrouter.get("configured"):
            value = openrouter.get("value", "")
            assert "..." in value or "*" in value or len(value) <= 12

    def test_get_config_by_key_valid(self):
        """Test getting a specific config value."""
        result = get_config_by_key("MAX_RETRIES")
        assert "value" in result
        assert "configured" in result
        assert result["source"] == "environment"

    def test_get_config_by_key_invalid(self):
        """Test getting an invalid config key."""
        with pytest.raises(HTTPException) as exc_info:
            get_config_by_key("INVALID_KEY")
        assert exc_info.value.status_code == 404


class TestMaskApiKey:
    """Tests for API key masking utility."""

    def test_mask_short_key(self):
        """Test masking a key shorter than 12 chars."""
        result = mask_api_key("abc")
        assert result == "***"

    def test_mask_long_key(self):
        """Test masking a key longer than 12 chars."""
        result = mask_api_key("sk-ant-1234567890abcdef")
        assert result.startswith("sk-ant-1")
        assert "..." in result
        assert result.endswith("cdef")

    def test_mask_empty_key(self):
        """Test masking an empty key."""
        result = mask_api_key("")
        assert result == ""


class TestScriptEndpoints:
    """Tests for script library endpoints."""

    def test_list_scripts_empty(self, test_db):
        """Test listing scripts when none exist."""
        result = list_scripts(test_db)
        assert result == []

    def test_list_scripts(self, test_db, sample_script):
        """Test listing scripts."""
        result = list_scripts(test_db)
        assert len(result) == 1
        assert result[0]["fingerprint"] == "invoice-standard"

    def test_get_script(self, test_db, sample_script):
        """Test getting a specific script."""
        result = get_script("invoice-standard", test_db)
        assert result["fingerprint"] == "invoice-standard"
        assert "script_body" in result
        assert result["version"] == 1

    def test_get_script_not_found(self, test_db):
        """Test getting a non-existent script."""
        with pytest.raises(HTTPException) as exc_info:
            get_script("nonexistent", test_db)
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)


class TestExtractionEndpoints:
    """Tests for extraction endpoints."""

    def test_get_extraction_not_found(self, test_db):
        """Test getting a non-existent extraction result."""
        with pytest.raises(HTTPException) as exc_info:
            get_extraction(99999, test_db)
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    def test_get_extraction(self, test_db, sample_extraction_result):
        """Test getting an extraction result."""
        result = get_extraction(sample_extraction_result.id, test_db)
        assert result.result_id == sample_extraction_result.id
        assert result.filename == "test_invoice.pdf"
