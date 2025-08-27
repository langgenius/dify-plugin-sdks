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
        return self._dispatch_event(settings, request)

    def _dispatch_event(self, settings: Mapping[str, Any], request: Request) -> TriggerEventDispatch:
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
        self, subscription_id: str, credentials: Mapping[str, Any], subscription_metadata: Mapping[str, Any]
    ) -> Unsubscription:
        """
        Remove a trigger subscription.

        Args:
            subscription_id: The internal subscription identifier from the original Subscription

            credentials: Authentication credentials (same structure as subscribe).
                        May be updated credentials if the original ones expired.

            subscription_metadata: Metadata saved during subscription (from Subscription.metadata).
                                 May include:
                                 - "external_id": External service's webhook/subscription ID
                                 - "repository": Repository name for GitHub
                                 - "webhook_url": Original webhook URL
                                 - Any data needed to identify and delete the subscription

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
            >>> result = provider.unsubscribe(
            ...     subscription_id="sub_123",
            ...     credentials={"access_token": "ghp_abc123"},
            ...     subscription_metadata={"external_id": "12345", "repository": "owner/repo"}
            ... )
            >>> assert result.success == True
            >>> print(result.message)  # "Successfully unsubscribed webhook 12345"

            Failed unsubscription:
            >>> result = provider.unsubscribe(
            ...     subscription_id="sub_456",
            ...     credentials={"access_token": "invalid"},
            ...     subscription_metadata={"external_id": "67890"}
            ... )
            >>> assert result.success == False
            >>> print(result.error_code)  # "INVALID_CREDENTIALS"
            >>> print(result.message)     # "Authentication failed: Invalid token"
        """
        return self._unsubscribe(subscription_id, credentials, subscription_metadata)

    def _unsubscribe(
        self, subscription_id: str, credentials: Mapping[str, Any], subscription_metadata: Mapping[str, Any]
    ) -> Unsubscription:
        """
        Internal method to implement unsubscription logic.

        Subclasses must override this method to handle subscription removal.

        Implementation guidelines:
        1. Extract necessary IDs from subscription_metadata (e.g., external_id)
        2. For webhooks:
           - Use external service API to delete the webhook
           - Handle common errors (not found, unauthorized, etc.)
        3. For polling:
           - Just mark as inactive (no external call needed)
        4. Always return Unsubscription with detailed status
        5. Never raise exceptions for operational failures - use Unsubscription.success=False

        Args:
            subscription_id: Internal subscription ID
            credentials: Authentication credentials
            subscription_metadata: Metadata from original subscription

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


class Trigger(ABC):
    """
    The trigger interface
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
        return cls._fetch_parameter_options is not Trigger._fetch_parameter_options
