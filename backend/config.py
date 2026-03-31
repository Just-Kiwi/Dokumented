"""
Configuration module for Dokumented.
Loads environment variables from .env file.
All sensitive configuration (API keys) MUST be set via .env file for security.
"""
from dotenv import load_dotenv
import os

load_dotenv()

# API Keys (sensitive - read from environment only)
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./dokumented.db')

# Application settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.75'))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './documents')
MAX_BATCH_SIZE = int(os.getenv('MAX_BATCH_SIZE', '25'))
BATCH_DOWNLOAD_MODE = os.getenv('BATCH_DOWNLOAD_MODE', 'combined')


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
        "OPENROUTER_API_KEY": {
            "value": mask_api_key(OPENROUTER_API_KEY),
            "configured": bool(OPENROUTER_API_KEY),
            "source": "environment"
        },
        "OPENROUTER_BASE_URL": {
            "value": OPENROUTER_BASE_URL,
            "configured": bool(OPENROUTER_BASE_URL),
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
        },
        "MAX_BATCH_SIZE": {
            "value": str(MAX_BATCH_SIZE),
            "configured": True,
            "source": "environment"
        },
        "BATCH_DOWNLOAD_MODE": {
            "value": BATCH_DOWNLOAD_MODE,
            "configured": True,
            "source": "environment"
        }
    }
