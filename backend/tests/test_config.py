"""
Tests for config module.
"""
import pytest
import os


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_config_has_required_keys(self):
        """Test config module has all required configuration keys."""
        from config import (
            ANTHROPIC_API_KEY,
            MERCURY_API_KEY,
            MERCURY_BASE_URL,
            DATABASE_URL,
            MAX_RETRIES,
            CONFIDENCE_THRESHOLD,
            UPLOAD_FOLDER,
        )
        
        assert ANTHROPIC_API_KEY is not None
        assert MERCURY_API_KEY is not None
        assert MERCURY_BASE_URL is not None
        assert DATABASE_URL is not None
        assert MAX_RETRIES is not None
        assert CONFIDENCE_THRESHOLD is not None
        assert UPLOAD_FOLDER is not None

    def test_max_retries_is_integer(self):
        """Test MAX_RETRIES is converted to integer."""
        from config import MAX_RETRIES
        assert isinstance(MAX_RETRIES, int)
        assert MAX_RETRIES >= 1

    def test_confidence_threshold_is_float(self):
        """Test CONFIDENCE_THRESHOLD is converted to float."""
        from config import CONFIDENCE_THRESHOLD
        assert isinstance(CONFIDENCE_THRESHOLD, float)
        assert 0.0 <= CONFIDENCE_THRESHOLD <= 1.0

    def test_default_database_url(self):
        """Test default DATABASE_URL format."""
        from config import DATABASE_URL
        assert "sqlite" in DATABASE_URL.lower()

    def test_default_mercury_base_url(self):
        """Test default Mercury base URL."""
        from config import MERCURY_BASE_URL
        assert "inceptionlabs.ai" in MERCURY_BASE_URL


class TestConfigEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_env_variable_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("MAX_RETRIES", "10")
        monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.9")
        
        from importlib import reload
        import config
        reload(config)
        
        assert config.MAX_RETRIES == 10
        assert config.CONFIDENCE_THRESHOLD == 0.9
