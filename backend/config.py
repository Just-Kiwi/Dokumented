"""
Configuration module for DocFlow.
Loads environment variables from .env file.
"""
from dotenv import load_dotenv
import os

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
MERCURY_API_KEY = os.getenv('MERCURY_API_KEY', '')
MERCURY_BASE_URL = os.getenv('MERCURY_BASE_URL', 'https://api.inceptionlabs.ai/v1')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./docflow.db')

# Application settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.75'))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './documents')
