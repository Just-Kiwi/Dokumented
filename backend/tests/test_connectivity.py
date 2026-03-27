"""
Connectivity tests for external APIs.
Requires valid API keys in .env file.
Run explicitly: pytest tests/test_connectivity.py -v
"""
import pytest
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


# ─────────────────────────────────────────────────────────────
# Configuration Validation
# ─────────────────────────────────────────────────────────────

class TestConfiguration:
    """Verify API keys are configured in .env."""

    def test_openrouter_key_present(self):
        """Check if OPENROUTER_API_KEY is set in .env."""
        assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY not set in .env file"


# ─────────────────────────────────────────────────────────────
# Network / DNS Connectivity
# ─────────────────────────────────────────────────────────────

class TestNetworkConnectivity:
    """Basic internet connectivity tests."""

    def test_dns_resolution_openrouter(self):
        """DNS can resolve OpenRouter API hostname."""
        host = OPENROUTER_BASE_URL.replace('https://', '').split('/')[0]
        try:
            socket.gethostbyname(host)
        except socket.gaierror as e:
            pytest.fail(f"DNS resolution failed for {host}: {e}")

    def test_tcp_connectivity_openrouter(self):
        """Can establish TCP connection to OpenRouter API on port 443."""
        host = OPENROUTER_BASE_URL.replace('https://', '').split('/')[0]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, 443))
            sock.close()
        except Exception as e:
            pytest.fail(f"Cannot connect to {host}:443: {e}")


# ─────────────────────────────────────────────────────────────
# API Authentication Tests (makes real API calls)
# ─────────────────────────────────────────────────────────────

class TestOpenRouterAPI:
    """Verify OpenRouter API accepts the configured key."""

    def test_openrouter_api_key_valid_claude(self):
        """OpenRouter API returns success for Claude model."""
        if not OPENROUTER_API_KEY:
            pytest.skip("OPENROUTER_API_KEY not configured in .env")
        
        from openai import OpenAI
        client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
        message = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        assert message.choices[0].message.content
        assert len(message.choices[0].message.content) > 0

    def test_openrouter_api_key_valid_mercury(self):
        """OpenRouter API returns success for Mercury model."""
        if not OPENROUTER_API_KEY:
            pytest.skip("OPENROUTER_API_KEY not configured in .env")
        
        from openai import OpenAI
        client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
        message = client.chat.completions.create(
            model="inception-ai/Mercury-2",
            max_tokens=10,
            messages=[{"role": "user", "content": "hello"}]
        )
        assert message is not None

    def test_openrouter_credits_available(self):
        """Verify OpenRouter API has credits available."""
        if not OPENROUTER_API_KEY:
            pytest.skip("OPENROUTER_API_KEY not configured in .env")
        
        from openai import OpenAI
        from openai import APIError as OpenAIAPIError
        
        client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
        try:
            message = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            assert message.choices[0].message.content
        except OpenAIAPIError as e:
            error_str = str(e).lower()
            if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                pytest.fail(f"OpenRouter API has insufficient credits: {e}")
            raise


# ─────────────────────────────────────────────────────────────
# Integration: Test Credit Check Endpoint
# ─────────────────────────────────────────────────────────────

class TestCreditCheckEndpoint:
    """Test the /api/credits endpoint functionality."""
    
    def test_credit_check_returns_status(self):
        """Test credit check endpoint returns correct status structure."""
        from main import check_credits
        
        result = check_credits()
        
        assert result.anthropic is not None
        assert result.mercury is not None
        assert "OpenRouter" in result.anthropic.provider
        assert "OpenRouter" in result.mercury.provider
