"""
Exceptions for trigger-related operations
"""


class TriggerError(Exception):
    """Base exception for all trigger-related errors"""

    pass


class SubscriptionError(TriggerError):
    """
    Raised when trigger subscription operations fail.

    This exception is raised for various subscription failures:
    - Invalid credentials or authentication failures
    - Network errors when contacting external services
    - Invalid subscription parameters
    - External service API errors (rate limits, service unavailable, etc.)
    """

    def __init__(self, message: str, error_code: str | None = None, external_response: dict | None = None):
        """
        Initialize SubscriptionError with detailed information.

        Args:
            message: Human-readable error description
            error_code: Machine-readable error code for categorization
            external_response: Raw response from external service (if available)
        """
        super().__init__(message)
        self.error_code = error_code
        self.external_response = external_response


class WebhookValidationError(TriggerError):
    """
    Raised when webhook signature validation fails.

    This indicates potential security issues where the webhook
    request cannot be verified as coming from the expected source.
    """

    pass


class TriggerDispatchError(TriggerError):
    """
    Raised when event dispatching fails.

    This can occur when:
    - Event payload cannot be parsed
    - Event type cannot be determined
    - Required headers are missing
    """

    pass
