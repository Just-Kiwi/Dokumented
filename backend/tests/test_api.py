"""
Tests for API endpoints using direct function calls instead of TestClient.
"""
import pytest
from db.models import AppConfig, ScriptLibrary, ExtractionResult, StatusEnum
from main import app, set_config, get_config, list_config, get_script, list_scripts, get_extraction, health_check
from fastapi import HTTPException


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health check returns OK."""
        response = health_check()
        assert response["status"] == "ok"
        assert response["service"] == "Dokumented API"


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_set_config(self, test_db):
        """Test setting a configuration value."""
        from models.schemas import ConfigUpdate
        update = ConfigUpdate(key="ANTHROPIC_API_KEY", value="sk-ant-test")
        result = set_config(update, test_db)
        assert result.key == "ANTHROPIC_API_KEY"
        assert result.value == "sk-ant-test"

    def test_set_config_invalid_key(self, test_db):
        """Test setting an invalid config key."""
        from models.schemas import ConfigUpdate
        update = ConfigUpdate(key="INVALID_KEY", value="some-value")
        with pytest.raises(HTTPException) as exc_info:
            set_config(update, test_db)
        assert exc_info.value.status_code == 400
        assert "not allowed" in str(exc_info.value.detail)

    def test_get_config(self, test_db, sample_config):
        """Test getting a specific config value."""
        result = get_config("ANTHROPIC_API_KEY", test_db)
        assert result.key == "ANTHROPIC_API_KEY"

    def test_get_config_invalid_key(self, test_db):
        """Test getting an invalid config key."""
        with pytest.raises(HTTPException) as exc_info:
            get_config("INVALID_KEY", test_db)
        assert exc_info.value.status_code == 400
        assert "not allowed" in str(exc_info.value.detail)

    def test_list_config(self, test_db, sample_config):
        """Test listing all configurations."""
        result = list_config(test_db)
        assert "ANTHROPIC_API_KEY" in result
        assert "MERCURY_API_KEY" in result

    def test_list_config_hides_api_key_values(self, test_db, sample_config):
        """Test that API key values are not exposed in list."""
        result = list_config(test_db)
        assert result["ANTHROPIC_API_KEY"]["exists"] is True
        assert "value" not in result["ANTHROPIC_API_KEY"]


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
