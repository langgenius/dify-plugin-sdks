from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities import ParameterOption
from dify_plugin.entities.trigger import (
    Subscription,
    TriggerEvent,
    TriggerEventDispatch,
    TriggerRuntime,
    Unsubscription,
)
from dify_plugin.errors.trigger import (
    SubscriptionError,
    TriggerDispatchError,
    WebhookValidationError,
)


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

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return self._oauth_get_credentials(system_credentials, request)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        raise NotImplementedError("This plugin should implement `_oauth_get_credentials` method to enable oauth")

    def dispatch_event(self, settings: Mapping[str, Any], request: Request) -> TriggerEventDispatch:
        """
        Dispatch an incoming webhook event to the appropriate trigger handler.

        This method is called when an external service sends an event to the webhook endpoint.
        The provider should validate the request, determine the event type, and return
        information about how to route this event to the correct trigger.

        Args:
            settings: Subscription-specific settings for this webhook endpoint.
                     Structure defined in provider's subscription_schema.
                     This is the same data that was passed as subscription_params during subscribe().
                     May include:
                     - "webhook_secret": Secret for signature validation
                     - "events": List of subscribed event types
                     - "repository": Target repository for GitHub
                     - Any configuration specific to this subscription

            request: The incoming HTTP request from the external service.
                    Contains headers, body, and other HTTP request data.
                    Use this to:
                    - Validate webhook signatures (using settings.webhook_secret)
                    - Extract event type from headers
                    - Parse event payload from body

        Returns:
            TriggerEventDispatch: Contains:
                                - event: The event type/name to dispatch
                                - response: HTTP response to return to the webhook caller

        Raises:
            WebhookValidationError: If signature validation fails
            TriggerDispatchError: If event cannot be parsed or routed

        Example:
            >>> # GitHub webhook dispatch
            >>> def _dispatch_event(self, settings, request):
            ...     # Validate signature using settings
            ...     secret = settings.get("webhook_secret")
            ...     if not self._validate_signature(request, secret):
            ...         raise WebhookValidationError("Invalid signature")
            ...
            ...     # Determine event type
            ...     event_type = request.headers.get("X-GitHub-Event")
            ...
            ...     # Return dispatch information
            ...     return TriggerEventDispatch(
            ...         event=event_type,  # e.g., "push", "pull_request"
            ...         response=Response("OK", status=200)
            ...     )
        """
        return self._dispatch_event(settings, request)

    def _dispatch_event(self, settings: Mapping[str, Any], request: Request) -> TriggerEventDispatch:
        """
        Internal method to implement event dispatch logic.

        Subclasses must override this method to handle incoming webhook events.

        Implementation checklist:
        1. Validate the webhook request:
           - Check signature/HMAC using webhook_secret from settings
           - Verify request is from expected source
        2. Extract event information:
           - Parse event type from headers or body
           - Extract relevant payload data
        3. Return TriggerEventDispatch with:
           - event: String identifying the event type
           - response: Appropriate HTTP response for the webhook

        Args:
            settings: Subscription settings from subscription_schema (same as subscription_params)
            request: Incoming webhook HTTP request

        Returns:
            TriggerEventDispatch: Event routing information

        Raises:
            WebhookValidationError: For security validation failures
            TriggerDispatchError: For parsing or routing errors
        """
        raise NotImplementedError("This plugin should implement `_dispatch_event` method to enable event dispatch")

    def subscribe(self, credentials: Mapping[str, Any], subscription_params: Mapping[str, Any]) -> Subscription:
        """
        Create a trigger subscription with the external service.

        This method handles different trigger patterns:
        - Push-based (Webhook): Registers a callback URL with the external service
        - Pull-based (Polling): Configures polling parameters (no external registration)

        Args:
            credentials: Authentication credentials for the external service.
                        Structure depends on provider's credentials_schema.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth
                        - {} for services that don't require auth

            subscription_params: Parameters for creating the subscription.
                               Structure depends on trigger type and provider's subscription_schema.

                               For WEBHOOK triggers, Dify automatically injects:
                               - "callback_url" (str): The endpoint URL allocated by Dify for receiving webhooks
                                 Example: "https://dify.ai/webhooks/sub_abc123"

                               Additional parameters from subscription_schema may include:
                               - "webhook_secret" (str): Secret for webhook signature validation
                               - "events" (list[str]): Event types to subscribe to
                               - "repository" (str): Target repository for GitHub
                               - "channel" (str): Target channel for Slack

                               For POLLING triggers, parameters may include:
                               - "interval" (int): Polling interval in seconds
                               - "target_endpoint" (str): API endpoint to poll
                               - "filters" (dict): Filtering criteria

        Returns:
            Subscription: Contains subscription details including:
                         - subscription_id: Unique identifier
                         - external_id: ID from external service (if applicable)
                         - metadata: Provider-specific data for future operations

        Raises:
            SubscriptionError: If subscription fails (e.g., invalid credentials, API errors)
            ValueError: If required parameters are missing or invalid

        Examples:
            GitHub webhook subscription:
            >>> result = provider.subscribe(
            ...     credentials={"access_token": "ghp_abc123"},
            ...     subscription_params={
            ...         "callback_url": "https://dify.ai/webhooks/sub_123",  # Injected by Dify
            ...         "webhook_secret": "whsec_abc...",  # From subscription_schema
            ...         "repository": "owner/repo",  # From subscription_schema
            ...         "events": ["push", "pull_request"]  # From subscription_schema
            ...     }
            ... )
            >>> print(result.subscription_id)  # "sub_123"
            >>> print(result.external_id)     # GitHub webhook ID

            RSS polling subscription:
            >>> result = provider.subscribe(
            ...     credentials={},  # RSS doesn't need credentials
            ...     subscription_params={
            ...         "feed_url": "https://example.com/rss",  # From subscription_schema
            ...         "interval": 300,  # Poll every 5 minutes
            ...         "filters": {"category": "tech"}
            ...     }
            ... )
        """
        return self._subscribe(credentials, subscription_params)

    def _subscribe(self, credentials: Mapping[str, Any], subscription_params: Mapping[str, Any]) -> Subscription:
        """
        Internal method to implement subscription logic.

        Subclasses must override this method to handle subscription creation.

        Implementation checklist:
        1. Determine trigger type by checking for 'callback_url' in subscription_params
        2. For webhooks:
           - Extract callback_url from subscription_params
           - Register webhook with external service using their API
           - Store returned webhook ID in metadata
        3. For polling:
           - Validate polling configuration
           - No external registration needed
        4. Return Subscription with all necessary metadata

        Args:
            credentials: Authentication credentials
            subscription_params: Subscription parameters

        Returns:
            Subscription: Subscription details with metadata for future operations

        Raises:
            SubscriptionError: For operational failures (API errors, invalid credentials)
            ValueError: For programming errors (missing required params)
        """
        raise NotImplementedError("This plugin should implement `_subscribe` method to enable event subscription")

    def unsubscribe(
        self, subscription: Subscription, credentials: Mapping[str, Any], settings: Mapping[str, Any]
    ) -> Unsubscription:
        """
        Remove a trigger subscription.

        Args:
            subscription: The Subscription object returned from subscribe() or resubscribe().
                         Contains expire_at and metadata with all necessary information.

            credentials: Authentication credentials for the external service.
                        Structure defined in provider's credentials_schema.
                        May contain refreshed tokens if OAuth tokens were renewed.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth

            settings: Provider-specific settings for this subscription.
                     Structure defined in provider's subscription_schema.
                     Contains configuration that may affect unsubscription behavior.

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
            ...     expire_at=1234567890,
            ...     metadata={"external_id": "12345", "repository": "owner/repo"}
            ... )
            >>> result = provider.unsubscribe(
            ...     subscription=subscription,
            ...     credentials={"access_token": "ghp_abc123"},  # From credentials_schema
            ...     settings={"events": ["push", "pull_request"]}  # From subscription_schema
            ... )
            >>> assert result.success == True
            >>> print(result.message)  # "Successfully unsubscribed webhook 12345"

            Failed unsubscription:
            >>> result = provider.unsubscribe(
            ...     subscription=subscription,
            ...     credentials={"access_token": "invalid"},
            ...     settings={}
            ... )
            >>> assert result.success == False
            >>> print(result.error_code)  # "INVALID_CREDENTIALS"
            >>> print(result.message)     # "Authentication failed: Invalid token"
        """
        return self._unsubscribe(subscription, credentials, settings)

    def _unsubscribe(
        self, subscription: Subscription, credentials: Mapping[str, Any], settings: Mapping[str, Any]
    ) -> Unsubscription:
        """
        Internal method to implement unsubscription logic.

        Subclasses must override this method to handle subscription removal.

        Implementation guidelines:
        1. Extract necessary IDs from subscription.metadata (e.g., external_id)
        2. For webhooks:
           - Use external service API to delete the webhook
           - Handle common errors (not found, unauthorized, etc.)
        3. For polling:
           - Just mark as inactive (no external call needed)
        4. Always return Unsubscription with detailed status
        5. Never raise exceptions for operational failures - use Unsubscription.success=False

        Args:
            subscription: The Subscription object with metadata
            credentials: Authentication credentials from credentials_schema
            settings: Provider settings from subscription_schema

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
        - A subscription is approaching expiration (check expire_at timestamp)
        - You want to keep the subscription active with the same settings
        - No configuration changes are needed

        For updating subscription configuration, use resubscribe() instead.

        Args:
            subscription: The current Subscription object to refresh.
                         Contains expire_at and metadata with all configuration.

            credentials: Current authentication credentials for the external service.
                        Structure defined in provider's credentials_schema.
                        Examples:
                        - {"access_token": "ghp_..."} for GitHub
                        - {"api_key": "sk-..."} for API key auth

        Returns:
            Subscription: Refreshed subscription with:
                         - expire_at: Extended expiration timestamp
                         - metadata: Same metadata (configuration unchanged)

        Raises:
            SubscriptionError: If refresh fails (e.g., invalid credentials, API errors)
            ValueError: If required parameters are missing or invalid

        Examples:
            Refresh webhook subscription:
            >>> current_sub = Subscription(
            ...     expire_at=1234567890,  # Expiring soon
            ...     metadata={
            ...         "external_id": "12345",
            ...         "callback_url": "https://dify.ai/webhooks/sub_123",
            ...         "events": ["push", "pull_request"]
            ...     }
            ... )
            >>> result = provider.refresh(
            ...     subscription=current_sub,
            ...     credentials={"access_token": "ghp_abc123"}
            ... )
            >>> print(result.expire_at)  # Extended timestamp
            >>> print(result.metadata)  # Same configuration

            Refresh polling subscription:
            >>> current_sub = Subscription(
            ...     expire_at=1234567890,
            ...     metadata={"feed_url": "https://example.com/rss", "interval": 300}
            ... )
            >>> result = provider.refresh(
            ...     subscription=current_sub,
            ...     credentials={}
            ... )
            >>> print(result.expire_at)  # Extended by default duration
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
           - Simply extend the expire_at timestamp
           - No external API calls typically needed

        3. For lease-based subscriptions (e.g., Microsoft Graph):
           - Call service's lease renewal API
           - Handle renewal limits (some services limit renewal count)

        Args:
            subscription: Current subscription with metadata
            credentials: Current authentication credentials from credentials_schema

        Returns:
            Subscription: Same subscription with extended expiration

        Raises:
            SubscriptionError: For operational failures (API errors, invalid credentials)
            ValueError: For programming errors (missing required params)
        """
        raise NotImplementedError("This plugin should implement `_refresh` method to enable subscription refresh")

    def resubscribe(
        self, subscription: Subscription, credentials: Mapping[str, Any], settings: Mapping[str, Any]
    ) -> Subscription:
        """
        Update an existing subscription with new configuration settings.

        This method is used to modify a subscription's configuration, such as:
        - Changing subscribed events (e.g., add/remove push, pull_request events)
        - Updating filters or parameters
        - Modifying webhook settings
        - Changing polling intervals or targets

        Note: This also extends the subscription's expiration. If you only need to extend
        expiration without changing configuration, use refresh() instead.

        Args:
            subscription: The current Subscription object to update.
                         Contains expire_at and metadata with current configuration.

            credentials: Current authentication credentials for the external service.
                        Structure defined in provider's credentials_schema.
                        May contain refreshed tokens if OAuth tokens were renewed.
                        Examples:
                        - {"access_token": "new_ghp_..."} for GitHub with refreshed token
                        - {"api_key": "sk-..."} for API key auth

            settings: New configuration settings for this subscription.
                     Structure defined in provider's subscription_schema.
                     These settings REPLACE the current configuration.
                     Examples:
                     - {"events": ["push", "issue"], "repository": "owner/repo"}  # Changed events
                     - {"interval": 600, "filters": {"label": "bug"}}  # New polling config

        Returns:
            Subscription: Updated subscription with:
                         - expire_at: New expiration timestamp
                         - metadata: Updated to reflect new configuration
                         - May have new external_id if webhook was recreated

        Raises:
            SubscriptionError: If update fails (e.g., invalid credentials, API errors)
            ValueError: If required parameters are missing or invalid

        Examples:
            Update webhook to subscribe to different events:
            >>> current_sub = Subscription(
            ...     expire_at=1234567890,
            ...     metadata={
            ...         "external_id": "12345",
            ...         "callback_url": "https://dify.ai/webhooks/sub_123",
            ...         "events": ["push"]  # Currently only subscribed to push
            ...     }
            ... )
            >>> result = provider.resubscribe(
            ...     subscription=current_sub,
            ...     credentials={"access_token": "ghp_abc123"},
            ...     settings={"events": ["push", "pull_request", "issues"]}  # Add more events
            ... )
            >>> print(result.metadata["events"])  # ["push", "pull_request", "issues"]

            Update polling configuration:
            >>> current_sub = Subscription(
            ...     expire_at=1234567890,
            ...     metadata={"feed_url": "https://example.com/rss", "interval": 300}
            ... )
            >>> result = provider.resubscribe(
            ...     subscription=current_sub,
            ...     credentials={},
            ...     settings={"interval": 600, "filters": {"category": "tech"}}  # Change interval and add filters
            ... )
            >>> print(result.metadata["interval"])  # 600
        """
        return self._resubscribe(subscription, credentials, settings)

    def _resubscribe(
        self, subscription: Subscription, credentials: Mapping[str, Any], settings: Mapping[str, Any]
    ) -> Subscription:
        """
        Internal method to implement subscription update logic.

        Subclasses must override this method to handle subscription configuration updates.

        Implementation patterns:
        1. For webhooks:
           - Delete existing webhook using subscription.metadata.external_id
           - Create new webhook with updated settings
           - Return new Subscription with new external_id and metadata

        2. For polling subscriptions:
           - Update internal configuration based on new settings
           - Extend expire_at timestamp
           - Return Subscription with updated metadata

        3. For services with update APIs:
           - Call service's update/patch API with new settings
           - Handle partial vs full updates based on service capabilities
           - Update metadata to reflect new configuration

        Args:
            subscription: Current subscription with metadata
            credentials: Current authentication credentials from credentials_schema
            settings: New configuration from subscription_schema (replaces old settings)

        Returns:
            Subscription: Updated subscription with new configuration and expiration

        Raises:
            SubscriptionError: For operational failures (API errors, invalid credentials)
            ValueError: For programming errors (missing required params)
        """
        raise NotImplementedError("This plugin should implement `_resubscribe` method to enable subscription updates")


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
    def _trigger(self, request: Request, values: Mapping[str, Any], parameters: Mapping[str, Any]) -> TriggerEvent:
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

    def trigger(self, request: Request, values: Mapping[str, Any], parameters: Mapping[str, Any]) -> TriggerEvent:
        """
        Trigger the trigger with the given request.
        """
        return self._trigger(request, values, parameters)

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        return self._fetch_parameter_options(parameter)

    @classmethod
    def _is_fetch_parameter_options_overridden(cls) -> bool:
        """
        Check if the _fetch_parameter_options method is overridden by the subclass
        """
        return cls._fetch_parameter_options is not TriggerEvent._fetch_parameter_options
