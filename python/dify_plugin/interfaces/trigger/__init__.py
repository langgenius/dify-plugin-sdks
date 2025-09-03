from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities import ParameterOption
from dify_plugin.entities.oauth import OAuthCredentials, TriggerOAuthCredentials
from dify_plugin.entities.trigger import (
    Event,
    Subscription,
    TriggerDispatch,
    TriggerRuntime,
    Unsubscription,
)
from dify_plugin.errors.trigger import SubscriptionError, TriggerDispatchError

__all__ = [
    "SubscriptionError",
    "TriggerDispatchError",
    "TriggerEvent",
    "TriggerProvider",
]


class TriggerProvider:
    """
    Base class for trigger providers that manage trigger subscriptions and event dispatching.

    A trigger provider acts as a bridge between external services and Dify's trigger system,
    handling both push-based (webhook) and pull-based (polling) trigger patterns.

    Responsibilities:
    1. Subscribe/unsubscribe triggers with external services
    2. Dispatch incoming events to appropriate trigger handlers
    3. Manage authentication (OAuth/API keys)
    4. Validate webhook signatures and handle security

    Example implementations:
    - GitHub webhook provider: Manages GitHub webhooks and dispatches push/PR events
    - RSS polling provider: Polls RSS feeds and dispatches new item events
    - Slack webhook provider: Handles Slack event subscriptions
    """

    def validate_credentials(self, credentials: dict):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: dict):
        raise NotImplementedError(
            "This plugin should implement `_validate_credentials` method to enable credentials validation"
        )

    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(system_credentials)

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This plugin should implement `_oauth_get_authorization_url` method to enable oauth")

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> OAuthCredentials:
        credentials = self._oauth_get_credentials(system_credentials, request)
        return OAuthCredentials(
            expires_at=credentials.expires_at,
            credentials=credentials.credentials,
        )

    def _oauth_get_credentials(
        self, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        raise NotImplementedError("This plugin should implement `_oauth_get_credentials` method to enable oauth")

    def dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Dispatch an incoming webhook event to the appropriate trigger handler.

        This method is called when an external service sends an event to the webhook endpoint.
        The provider should validate the request, determine the event type, and return
        information about how to route this event to the correct trigger.

        Args:
            subscription: The Subscription object containing:
                         - endpoint: The webhook endpoint URL
                         - properties: All subscription configuration including:
                           * webhook_secret: Secret for signature validation
                           * events: List of subscribed event types
                           * repository: Target repository (for GitHub)
                           * Any other provider-specific configuration

            request: The incoming HTTP request from the external service.
                    Contains headers, body, and other HTTP request data.
                    Use this to:
                    - Validate webhook signatures (using subscription.data['webhook_secret'])
                    - Extract event type from headers
                    - Parse event payload from body

        Returns:
            TriggerDispatch: Contains:
                                - triggers: List of trigger names to dispatch (each triggers its workflow)
                                - response: HTTP response to return to the webhook caller

        Raises:
            TriggerValidationError: If signature validation fails
            TriggerDispatchError: If event cannot be parsed or routed

        Example:
            >>> # GitHub webhook dispatch
            >>> def _dispatch_event(self, subscription, request):
            ...     # Validate signature using subscription properties
            ...     secret = subscription.properties.get("webhook_secret")
            ...     if not self._validate_signature(request, secret):
            ...         raise TriggerValidationError("Invalid signature")
            ...
            ...     # Determine event type
            ...     event_type = request.headers.get("X-GitHub-Event")
            ...
            ...     # Return dispatch information
            ...     return TriggerEventDispatch(
            ...         triggers=[event_type],  # e.g., ["push"], ["pull_request"]
            ...         response=Response("OK", status=200)
            ...     )
            ...
            ...     # Or dispatch multiple events from one webhook
            ...     return TriggerEventDispatch(
            ...         triggers=["issues", "issues.opened"],  # Trigger multiple workflows
            ...         response=Response("OK", status=200)
            ...     )
        """
        return self._dispatch_event(subscription, request)

    def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
        """
        Internal method to implement event dispatch logic.

        Subclasses must override this method to handle incoming webhook events.

        Implementation checklist:
        1. Validate the webhook request:
           - Check signature/HMAC using webhook_secret from subscription.properties
           - Verify request is from expected source
        2. Extract event information:
           - Parse event type from headers or body
           - Extract relevant payload data
        3. Return TriggerDispatch with:
           - triggers: List of trigger names to dispatch (can be single or multiple)
           - response: Appropriate HTTP response for the webhook

        Args:
            subscription: The Subscription object with endpoint and properties fields
            request: Incoming webhook HTTP request

        Returns:
            TriggerDispatch: Trigger routing information

        Raises:
            TriggerValidationError: For security validation failures
            TriggerDispatchError: For parsing or routing errors
        """
        raise NotImplementedError("This plugin should implement `_dispatch_event` method to enable event dispatch")

    def subscribe(self, endpoint: str, credentials: Mapping[str, Any], parameters: Mapping[str, Any]) -> Subscription:
        """
        Create a trigger subscription with the external service.

        This method handles different trigger patterns:
        - Push-based (Webhook): Registers a callback URL with the external service
        - Pull-based (Polling): Configures polling parameters (no external registration)

        Args:
            endpoint: The webhook endpoint URL allocated by Dify for receiving events

            credentials: Authentication credentials for the external service.
                        Structure depends on provider's credentials_schema.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth
                        - {} for services that don't require auth

            parameters: Parameters for creating the subscription.
                        Structure depends on provider's parameters_schema.

                        Dify automatically injects:
                        - "endpoint" (str): The webhook endpoint URL allocated by Dify for receiving events
                          Example: "https://dify.ai/webhooks/sub_abc123"

                        Additional parameters from parameters_schema may include:
                               - "webhook_secret" (str): Secret for webhook signature validation
                               - "events" (list[str]): Event types to subscribe to
                               - "repository" (str): Target repository for GitHub
                               - Other provider-specific configuration

        Returns:
            Subscription: Contains subscription details including:
                         - expires_at: Expiration timestamp
                         - endpoint: The webhook endpoint URL
                         - parameters: The parameters of the subscription
                         - properties: Provider-specific configuration and metadata

        Raises:
            SubscriptionError: If subscription fails (e.g., invalid credentials, API errors)
            ValueError: If required parameters are missing or invalid

        Examples:
            GitHub webhook subscription:
            >>> result = provider.subscribe(
            ...     credentials={"access_token": "ghp_abc123"},
            ...     parameters={
            ...         "webhook_secret": "whsec_abc...",  # From properties_schema
            ...         "repository": "owner/repo",  # From parameters_schema
            ...         "events": ["push", "pull_request"]  # From parameters_schema
            ...     }
            ... )
            >>> print(result.endpoint)  # "https://dify.ai/webhooks/sub_123"
            >>> print(result.properties["external_id"])  # GitHub webhook ID
        """
        return self._subscribe(endpoint, credentials, parameters)

    def _subscribe(self, endpoint: str, credentials: Mapping[str, Any], parameters: Mapping[str, Any]) -> Subscription:
        """
        Internal method to implement subscription logic.

        Subclasses must override this method to handle subscription creation.

        Implementation checklist:
        1. Extract endpoint from parameters
        2. Register webhook with external service using their API
        3. Store all necessary information in Subscription.properties
        4. Return Subscription with:
           - expires_at: Set appropriate expiration time
           - endpoint: The webhook endpoint from parameters, injected by Dify
           - parameters: The parameters of the subscription
           - properties: All configuration and external IDs

        Args:
            endpoint: The webhook endpoint URL allocated by Dify for receiving events

            credentials: Authentication credentials
            parameters: Subscription parameters

        Returns:
            Subscription: Subscription details with metadata for future operations

        Raises:
            SubscriptionError: For operational failures (API errors, invalid credentials)
            ValueError: For programming errors (missing required params)
        """
        raise NotImplementedError("This plugin should implement `_subscribe` method to enable event subscription")

    def unsubscribe(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Unsubscription:
        """
        Remove a trigger subscription.

        Args:
            subscription: The Subscription object returned from subscribe().
                         Contains expires_at, endpoint, and properties with all necessary information.

            credentials: Authentication credentials for the external service.
                        Structure defined in provider's credentials_schema.
                        May contain refreshed tokens if OAuth tokens were renewed.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth

        Returns:
            Unsubscription: Detailed result of the unsubscription operation:
                          - success=True: Operation completed successfully
                          - success=False: Operation failed, check message and error_code

        Note:
            This method should never raise exceptions for operational failures.
            Use the Unsubscription result to communicate all outcomes.
            Only raise exceptions for programming errors (e.g., invalid parameters).

        Examples:
            Successful unsubscription:
            >>> subscription = Subscription(
            ...     expires_at=1234567890,
            ...     endpoint="https://dify.ai/webhooks/sub_123",
            ...     properties={"external_id": "12345", "repository": "owner/repo"}
            ... )
            >>> result = provider.unsubscribe(
            ...     subscription=subscription,
            ...     credentials={"access_token": "ghp_abc123"}  # From credentials_schema
            ... )
            >>> assert result.success == True
            >>> print(result.message)  # "Successfully unsubscribed webhook 12345"

            Failed unsubscription:
            >>> result = provider.unsubscribe(
            ...     subscription=subscription,
            ...     credentials={"access_token": "invalid"}
            ... )
            >>> assert result.success == False
            >>> print(result.error_code)  # "INVALID_CREDENTIALS"
            >>> print(result.message)     # "Authentication failed: Invalid token"
        """
        return self._unsubscribe(subscription, credentials)

    def _unsubscribe(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Unsubscription:
        """
        Internal method to implement unsubscription logic.

        Subclasses must override this method to handle subscription removal.

        Implementation guidelines:
        1. Extract necessary IDs from subscription.properties (e.g., external_id)
        2. Use external service API to delete the webhook
        3. Handle common errors (not found, unauthorized, etc.)
        4. Always return Unsubscription with detailed status
        5. Never raise exceptions for operational failures - use Unsubscription.success=False

        Args:
            subscription: The Subscription object with endpoint and properties fields
            credentials: Authentication credentials from credentials_schema

        Returns:
            Unsubscription: Always returns result, never raises for operational failures

        Common error_codes:
        - "WEBHOOK_NOT_FOUND": External webhook doesn't exist
        - "INVALID_CREDENTIALS": Authentication failed
        - "API_ERROR": External service API error
        - "NETWORK_ERROR": Connection issues
        - "RATE_LIMITED": API rate limit exceeded
        """
        raise NotImplementedError("This plugin should implement `_unsubscribe` method to enable event unsubscription")

    def refresh(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        """
        Refresh/extend an existing subscription without changing its configuration.

        This is a lightweight operation that simply extends the subscription's expiration time
        while keeping all settings and configuration unchanged. Use this when:
        - A subscription is approaching expiration (check expires_at timestamp)
        - You want to keep the subscription active with the same settings
        - No configuration changes are needed


        Args:
            subscription: The current Subscription object to refresh.
                         Contains expires_at and properties with all configuration.

            credentials: Current authentication credentials for the external service.
                        Structure defined in provider's credentials_schema.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth

        Returns:
            Subscription: Refreshed subscription with:
                         - expires_at: Extended expiration timestamp
                         - properties: Same properties (configuration unchanged)

        Raises:
            SubscriptionError: If refresh fails (e.g., invalid credentials, API errors)
            ValueError: If required parameters are missing or invalid

        Examples:
            Refresh webhook subscription:
            >>> current_sub = Subscription(
            ...     expires_at=1234567890,  # Expiring soon
            ...     endpoint="https://dify.ai/webhooks/sub_123",
            ...     properties={
            ...         "external_id": "12345",
            ...         "events": ["push", "pull_request"],
            ...         "repository": "owner/repo"
            ...     }
            ... )
            >>> result = provider.refresh(
            ...     subscription=current_sub,
            ...     credentials={"access_token": "ghp_abc123"}
            ... )
            >>> print(result.expires_at)  # Extended timestamp
            >>> print(result.properties)  # Same configuration

            Refresh polling subscription:
            >>> current_sub = Subscription(
            ...     expires_at=1234567890,
            ...     endpoint="https://dify.ai/webhooks/sub_456",
            ...     properties={"feed_url": "https://example.com/rss", "interval": 300}
            ... )
            >>> result = provider.refresh(
            ...     subscription=current_sub,
            ...     credentials={}
            ... )
            >>> print(result.expires_at)  # Extended by default duration
        """
        return self._refresh(subscription, credentials)

    def _refresh(self, subscription: Subscription, credentials: Mapping[str, Any]) -> Subscription:
        """
        Internal method to implement subscription refresh logic.

        Subclasses must override this method to handle simple expiration extension.

        Implementation patterns:
        1. For webhooks with expiration:
           - Call service's refresh/extend API if available
           - Or re-register with same settings if needed
           - Keep same external_id if possible

        2. For polling subscriptions:
           - Simply extend the expires_at timestamp
           - No external API calls typically needed

        3. For lease-based subscriptions (e.g., Microsoft Graph):
           - Call service's lease renewal API
           - Handle renewal limits (some services limit renewal count)

        Args:
            subscription: Current subscription with properties
            credentials: Current authentication credentials from credentials_schema

        Returns:
            Subscription: Same subscription with extended expiration

        Raises:
            SubscriptionError: For operational failures (API errors, invalid credentials)
            ValueError: For programming errors (missing required params)
        """
        raise NotImplementedError("This plugin should implement `_refresh` method to enable subscription refresh")


class TriggerEvent(ABC):
    """
    The trigger event interface
    """

    runtime: TriggerRuntime
    session: Session

    @final
    def __init__(
        self,
        runtime: TriggerRuntime,
        session: Session,
    ):
        """
        Initialize the trigger

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Trigger the trigger with the given request.

        To be implemented by subclasses.
        """

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.

        To be implemented by subclasses.

        Also, it's optional to implement, that's why it's not an abstract method.
        """
        raise NotImplementedError(
            "This plugin should implement `_fetch_parameter_options` method to enable dynamic select parameter"
        )

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Trigger the trigger with the given request.
        """
        return self._trigger(request, parameters)

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        return self._fetch_parameter_options(parameter)
