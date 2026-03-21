"""
Connectivity tests for external APIs.
Requires valid API keys in .env.
Run explicitly: pytest tests/test_connectivity.py -v
"""
import pytest
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ANTHROPIC_API_KEY, MERCURY_API_KEY, MERCURY_BASE_URL


# ─────────────────────────────────────────────────────────────
# Configuration Validation
# ─────────────────────────────────────────────────────────────

class TestConfiguration:
    """Verify API keys are configured."""

    def test_anthropic_key_present(self):
        """Check if ANTHROPIC_API_KEY is set in .env."""
        assert ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY not set in .env"

    def test_mercury_key_present(self):
        """Check if MERCURY_API_KEY is set in .env."""
        assert MERCURY_API_KEY, "MERCURY_API_KEY not set in .env"


# ─────────────────────────────────────────────────────────────
# Network / DNS Connectivity
# ─────────────────────────────────────────────────────────────

class TestNetworkConnectivity:
    """Basic internet connectivity tests."""

    def test_dns_resolution_anthropic(self):
        """DNS can resolve Anthropic API hostname."""
        try:
            socket.gethostbyname('api.anthropic.com')
        except socket.gaierror as e:
            pytest.fail(f"DNS resolution failed for api.anthropic.com: {e}")

    def test_dns_resolution_mercury(self):
        """DNS can resolve Mercury/Inception Labs hostname."""
        host = MERCURY_BASE_URL.replace('https://', '').split('/')[0]
        try:
            socket.gethostbyname(host)
        except socket.gaierror as e:
            pytest.fail(f"DNS resolution failed for {host}: {e}")

    def test_tcp_connectivity_anthropic(self):
        """Can establish TCP connection to Anthropic API on port 443."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(('api.anthropic.com', 443))
            sock.close()
        except Exception as e:
            pytest.fail(f"Cannot connect to api.anthropic.com:443: {e}")

    def test_tcp_connectivity_mercury(self):
        """Can establish TCP connection to Mercury API on port 443."""
        host = MERCURY_BASE_URL.replace('https://', '').split('/')[0]
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

class TestAnthropicAPI:
    """Verify Anthropic API accepts the configured key."""

    @pytest.mark.skipif(not ANTHROPIC_API_KEY, reason="ANTHROPIC_API_KEY not configured")
    def test_anthropic_api_key_valid(self):
        """Anthropic API returns success for the configured key.
        
        Uses claude-3-haiku-4-20250514 (cheapest model) for testing.
        """
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-3-haiku-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        assert message.content[0].text
        assert len(message.content[0].text) > 0

    @pytest.mark.skipif(not ANTHROPIC_API_KEY, reason="ANTHROPIC_API_KEY not configured")
    def test_anthropic_credits_available(self):
        """Verify Anthropic API has credits available."""
        import anthropic
        from exceptions import AnthropicCreditError
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        try:
            message = client.messages.create(
                model="claude-3-haiku-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            assert message.content[0].text
        except Exception as e:
            error_str = str(e).lower()
            if "credit" in error_str or "quota" in error_str or "insufficient" in error_str:
                pytest.fail(f"Anthropic API has insufficient credits: {e}")
            raise


class TestMercuryAPI:
    """Verify Mercury/Inception Labs API accepts the configured key."""

    @pytest.mark.skipif(not MERCURY_API_KEY, reason="MERCURY_API_KEY not configured")
    def test_mercury_api_key_valid(self):
        """Mercury API returns success for the configured key.
        
        Mercury models are fast/costless for small prompts.
        """
        from openai import OpenAI
        client = OpenAI(api_key=MERCURY_API_KEY, base_url=MERCURY_BASE_URL)
        completion = client.chat.completions.create(
            model="mercury-coder-small-20b",
            max_tokens=10,
            messages=[{"role": "user", "content": "hello"}]
        )
        assert completion.choices[0].message.content
        assert len(completion.choices[0].message.content) > 0

    @pytest.mark.skipif(not MERCURY_API_KEY, reason="MERCURY_API_KEY not configured")
    def test_mercury_credits_available(self):
        """Verify Mercury API has credits available."""
        from openai import OpenAI
        from openai import APIError as OpenAIAPIError
        from exceptions import MercuryCreditError
        
        client = OpenAI(api_key=MERCURY_API_KEY, base_url=MERCURY_BASE_URL)
        try:
            completion = client.chat.completions.create(
                model="mercury-coder-small-20b",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            assert completion.choices[0].message.content
        except OpenAIAPIError as e:
            error_str = str(e).lower()
            if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                pytest.fail(f"Mercury API has insufficient credits: {e}")
            raise


# ─────────────────────────────────────────────────────────────
# Integration: Test Credit Check Endpoint
# ─────────────────────────────────────────────────────────────

class TestCreditCheckEndpoint:
    """Test the /api/credits endpoint functionality."""
    
    def test_credit_check_with_valid_keys(self, test_db):
        """Test credit check endpoint returns correct status."""
        from main import check_credits
        
        result = check_credits(test_db)
        
        assert result.anthropic is not None
        assert result.mercury is not None
        assert result.anthropic.provider == "Anthropic"
        assert result.mercury.provider == "Mercury/Inception Labs"
