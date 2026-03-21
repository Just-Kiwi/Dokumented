"""
Custom exceptions for Dokumented API errors.
"""


class APIError(Exception):
    """Base exception for API-related errors."""

    def __init__(self, message: str, provider: str, error_code: str = None):
        self.message = message
        self.provider = provider
        self.error_code = error_code
        super().__init__(self.message)


class AnthropicCreditError(APIError):
    """Raised when Anthropic API (Claude) has insufficient credits."""

    def __init__(self, message: str = None):
        default_msg = "Anthropic API (Claude) has insufficient credits. Add credits to continue."
        super().__init__(
            message=message or default_msg,
            provider="Anthropic",
            error_code="INSUFFICIENT_CREDITS"
        )


class MercuryCreditError(APIError):
    """Raised when Mercury/Inception Labs API has insufficient credits."""

    def __init__(self, message: str = None):
        default_msg = "Mercury/Inception Labs API has insufficient credits. Add credits to continue."
        super().__init__(
            message=message or default_msg,
            provider="Mercury/Inception Labs",
            error_code="INSUFFICIENT_CREDITS"
        )


class APITimeoutError(APIError):
    """Raised when an API request times out."""

    def __init__(self, provider: str, message: str = None):
        default_msg = f"{provider} API request timed out."
        super().__init__(
            message=message or default_msg,
            provider=provider,
            error_code="TIMEOUT"
        )


class APIConnectionError(APIError):
    """Raised when cannot connect to an API."""

    def __init__(self, provider: str, message: str = None):
        default_msg = f"Cannot connect to {provider} API."
        super().__init__(
            message=message or default_msg,
            provider=provider,
            error_code="CONNECTION_ERROR"
        )


class APIAuthenticationError(APIError):
    """Raised when API authentication fails."""

    def __init__(self, provider: str, message: str = None):
        default_msg = f"{provider} API authentication failed. Check your API key."
        super().__init__(
            message=message or default_msg,
            provider=provider,
            error_code="AUTHENTICATION_ERROR"
        )
