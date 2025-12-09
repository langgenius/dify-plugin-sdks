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


class UnsubscribeError(TriggerError):
    """
    Raised when trigger unsubscribe operations fail.
    """

    def __init__(self, message: str, error_code: str | None = None, external_response: dict | None = None):
        """
        Initialize UnsubscribeError with detailed information.
        """
        super().__init__(message)
        self.error_code = error_code
        self.external_response = external_response


class TriggerValidationError(TriggerError):
    """
    Raised when webhook signature validation fails.

    This indicates potential security issues where the webhook
    request cannot be verified as coming from the expected source.
    """

    pass


class TriggerProviderCredentialValidationError(TriggerError):
    """
    Raised when trigger provider credential validation fails.
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


class TriggerProviderOAuthError(TriggerError):
    """
    Raised when trigger provider OAuth fails.
    """

    pass


class EventIgnoreError(TriggerError):
    """
    Raised when an event should be ignored based on filter criteria.

    This is thrown by Event._on_event() when the webhook payload
    doesn't match user-configured filters (e.g., labels, authors, patterns).
    """

    pass
