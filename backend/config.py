"""
Configuration module for Dokumented.
Loads environment variables from .env file.
All sensitive configuration (API keys) MUST be set via .env file for security.
"""
from dotenv import load_dotenv
import os

load_dotenv()

# API Keys (sensitive - read from environment only)
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
MERCURY_API_KEY = os.getenv('MERCURY_API_KEY', '')
MERCURY_BASE_URL = os.getenv('MERCURY_BASE_URL', 'https://api.inceptionlabs.ai/v1')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./dokumented.db')

# Application settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.75'))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './documents')


def mask_api_key(key: str) -> str:
    """Mask an API key for safe display, showing first 8 and last 4 chars."""
    if not key:
        return ""
    if len(key) <= 12:
        return "*" * len(key)
    return f"{key[:8]}...{key[-4:]}"


def get_config() -> dict:
    """
    Get all configuration values from environment.
    API keys are masked for safe display.
    """
    return {
        "ANTHROPIC_API_KEY": {
            "value": mask_api_key(ANTHROPIC_API_KEY),
            "configured": bool(ANTHROPIC_API_KEY),
            "source": "environment"
        },
        "MERCURY_API_KEY": {
            "value": mask_api_key(MERCURY_API_KEY),
            "configured": bool(MERCURY_API_KEY),
            "source": "environment"
        },
        "MERCURY_BASE_URL": {
            "value": MERCURY_BASE_URL,
            "configured": bool(MERCURY_BASE_URL),
            "source": "environment"
        },
        "MAX_RETRIES": {
            "value": str(MAX_RETRIES),
            "configured": True,
            "source": "environment"
        },
        "CONFIDENCE_THRESHOLD": {
            "value": str(CONFIDENCE_THRESHOLD),
            "configured": True,
            "source": "environment"
        },
        "DATABASE_URL": {
            "value": DATABASE_URL,
            "configured": True,
            "source": "environment"
        },
        "UPLOAD_FOLDER": {
            "value": UPLOAD_FOLDER,
            "configured": True,
            "source": "environment"
        }
    }
