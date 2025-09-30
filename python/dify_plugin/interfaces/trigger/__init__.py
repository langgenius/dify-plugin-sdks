from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities import ParameterOption
from dify_plugin.entities.oauth import OAuthCredentials, TriggerOAuthCredentials
from dify_plugin.entities.trigger import (
    Variables,
    Subscription,
    EventDispatch,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
)
from dify_plugin.errors.trigger import SubscriptionError, TriggerDispatchError
from dify_plugin.protocol.oauth import OAuthProviderProtocol

__all__ = [
    "SubscriptionError",
    "TriggerDispatchError",
    "Event",
    "Trigger",
    "TriggerSubscriptionConstructor",
]


class Trigger(ABC):
    """
    Base class for triggers that receive and dispatch incoming webhook requests.

    A Trigger receives webhooks from external services and routes them to the appropriate
    Events for processing. It handles validation and determines which Events should be invoked.

    Responsibilities:
    1. Receive incoming webhook requests
    2. Validate webhook signatures and security
    3. Parse webhook payload to determine event type
    4. Dispatch to appropriate Event(s)
    5. Return HTTP response to webhook caller

    Note: Subscription management (create/delete/refresh) and OAuth flows are handled by
    TriggerSubscriptionConstructor, not Trigger.

    Example implementations:
    - GitHub Trigger: Validates GitHub webhooks and dispatches to issue/PR Events
    - Slack Trigger: Validates Slack webhooks and dispatches to message Events
    """

    session: Session

    @final
    def __init__(
        self,
        session: Session,
    ):
        """
        Initialize the Trigger.

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.session = session

    def dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        """
        Dispatch an incoming webhook to the appropriate Events.

        This method is called when an external service sends a webhook to the endpoint.
        The trigger should validate the request, determine the event type, and return
        information about which Events should process this webhook.

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
            EventDispatch: Contains:
                          - events: List of Event names to invoke (each triggers its workflow)
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
            ...     action = request.get_json().get("action")
            ...
            ...     # Return dispatch information
            ...     return EventDispatch(
            ...         events=["issue_opened"],  # Event name(s) to invoke
            ...         response=Response("OK", status=200)
            ...     )
            ...
            ...     # Or dispatch multiple Events from one webhook
            ...     return EventDispatch(
            ...         events=["issue_opened", "issue_labeled"],  # Multiple Events
            ...         response=Response("OK", status=200)
            ...     )
        """
        return self._dispatch_event(subscription, request)

    @abstractmethod
    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
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
        3. Return EventDispatch with:
           - events: List of Event names to invoke (can be single or multiple)
           - response: Appropriate HTTP response for the webhook

        Args:
            subscription: The Subscription object with endpoint and properties fields
            request: Incoming webhook HTTP request

        Returns:
            EventDispatch: Event dispatch routing information

        Raises:
            TriggerValidationError: For security validation failures
            TriggerDispatchError: For parsing or routing errors
        """
        raise NotImplementedError("This plugin should implement `_dispatch_event` method to enable event dispatch")


class TriggerSubscriptionConstructor(ABC, OAuthProviderProtocol):
    """
    Base class for managing trigger subscriptions with external services.

    The TriggerSubscriptionConstructor handles the lifecycle of webhook subscriptions,
    including creating webhooks with external services, managing credentials, and
    handling OAuth flows.

    Responsibilities:
    1. Create subscriptions with external services (e.g., create GitHub webhooks)
    2. Delete subscriptions when no longer needed
    3. Refresh subscriptions before they expire
    4. Validate credentials (API keys or OAuth tokens)
    5. Handle OAuth authorization flows
    6. Fetch dynamic parameter options (e.g., list of repositories)

    Note: This is separate from Trigger, which handles incoming webhook dispatch.

    Example implementations:
    - GitHub Constructor: Creates/deletes GitHub webhooks via GitHub API
    - Slack Constructor: Manages Slack event subscriptions via Slack API
    """

    runtime: TriggerSubscriptionConstructorRuntime | None
    session: Session | None

    def __init__(self, runtime: TriggerSubscriptionConstructorRuntime | None = None, session: Session | None = None):
        self.runtime = runtime
        self.session = session

    def validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        return self._validate_api_key(credentials=credentials)

    def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
        raise NotImplementedError(
            "This plugin should implement `_validate_api_key` method to enable credentials validation"
        )

    def oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        """
        Get the authorization url

        :param redirect_uri: redirect uri provided by dify api
        :param system_credentials: system credentials including client_id and client_secret which oauth schema defined
        :return: authorization url
        """
        return self._oauth_get_authorization_url(redirect_uri=redirect_uri, system_credentials=system_credentials)

    def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError(
            "The trigger you are using does not support OAuth, please implement `_oauth_get_authorization_url` method"
        )

    def oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> OAuthCredentials:
        """
        Get the credentials

        :param redirect_uri: redirect uri provided by dify api
        :param system_credentials: system credentials including client_id and client_secret which oauth schema defined
        :param request: raw http request
        :return: credentials
        """
        credentials: TriggerOAuthCredentials = self._oauth_get_credentials(
            redirect_uri=redirect_uri, system_credentials=system_credentials, request=request
        )
        return OAuthCredentials(
            expires_at=credentials.expires_at or -1,
            credentials=credentials.credentials,
        )

    def _oauth_get_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    ) -> TriggerOAuthCredentials:
        raise NotImplementedError(
            "The trigger you are using does not support OAuth, please implement `_oauth_get_credentials` method"
        )

    def oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        """
        Refresh the credentials

        :param redirect_uri: redirect uri provided by dify api
        :param system_credentials: system credentials including client_id and client_secret which oauth schema defined
        :param credentials: credentials
        :return: refreshed credentials
        """
        return self._oauth_refresh_credentials(
            redirect_uri=redirect_uri, system_credentials=system_credentials, credentials=credentials
        )

    def _oauth_refresh_credentials(
        self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    ) -> OAuthCredentials:
        raise NotImplementedError(
            "The trigger you are using does not support OAuth, please implement `_oauth_refresh_credentials` method"
        )

    def create_subscription(
        self, endpoint: str, credentials: Mapping[str, Any], selected_events: list[str], parameters: Mapping[str, Any]
    ) -> Subscription:
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
        return self._create_subscription(
            endpoint=endpoint, credentials=credentials, selected_events=selected_events, parameters=parameters
        )

    @abstractmethod
    def _create_subscription(
        self, endpoint: str, credentials: Mapping[str, Any], selected_events: list[str], parameters: Mapping[str, Any]
    ) -> Subscription:
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

    def delete_subscription(self, subscription: Subscription, credentials: Mapping[str, Any]) -> UnsubscribeResult:
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
        return self._delete_subscription(subscription=subscription, credentials=credentials)

    def _delete_subscription(self, subscription: Subscription, credentials: Mapping[str, Any]) -> UnsubscribeResult:
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
        return self._refresh(subscription=subscription, credentials=credentials)

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

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        if self.runtime is None:
            raise ValueError("Runtime is not initialized")
        return self._fetch_parameter_options(credentials=self.runtime.credentials, parameter=parameter)

    def _fetch_parameter_options(self, credentials: Mapping[str, Any], parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        raise NotImplementedError(
            "This plugin should implement `_fetch_parameter_options` method to enable dynamic select parameter"
        )


class Event(ABC):
    """
    Base class for events that transform incoming webhook payloads into workflow variables.

    An Event receives a raw webhook request and transforms it into structured Variables
    that can be consumed by workflows. Each event implements:
    1. Data transformation from provider-specific format to standard output
    2. Filtering logic based on user-defined parameters
    3. Parameter validation and option fetching

    Responsibilities:
    - Parse and validate webhook payload
    - Apply user-configured filters (e.g., label filters, author filters)
    - Extract and transform data into output_schema format
    - Return structured Variables with extracted data

    Example implementations:
    - IssueOpenedEvent: Transforms GitHub issue webhook into workflow variables
    - MessageTextEvent: Transforms WhatsApp message webhook into workflow variables

    Workflow:
    1. Trigger receives webhook → dispatch_event() → returns Event names
    2. Dify invokes the specified Event → _on_event() → returns Variables
    3. Variables are passed to the workflow for processing
    """

    # Optional context objects. They may be None in environments like schema generation
    # or static validation where execution context isn't initialized.
    session: Session

    @final
    def __init__(
        self,
        session: Session,
    ):
        """
        Initialize the Event.

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        - The `session` parameter may be None in contexts where execution
          is not happening (e.g., schema generation, documentation generation).
        """
        self.session = session

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform the incoming webhook request into structured Variables.

        This method should:
        1. Parse the webhook payload from the request
        2. Apply filtering logic based on parameters
        3. Extract relevant data matching the output_schema
        4. Return a structured Variables object

        Args:
            request: The incoming webhook HTTP request containing the raw payload.
                    Use request.get_json() to parse JSON body.
            parameters: User-configured parameters for filtering and transformation
                       (e.g., label filters, regex patterns, threshold values).
                       These come from the subscription configuration.

        Returns:
            Variables: Structured variables matching the output_schema
                      defined in the event's YAML configuration.

        Raises:
            EventIgnoreError: When the event should be filtered out based on parameters
            ValueError: When the payload is invalid or missing required fields

        Example:
            >>> def _on_event(self, request, parameters):
            ...     payload = request.get_json()
            ...
            ...     # Apply filters
            ...     if not self._matches_filters(payload, parameters):
            ...         raise EventIgnoreError()
            ...
            ...     # Transform data
            ...     return Variables(variables={
            ...         "title": payload["issue"]["title"],
            ...         "author": payload["issue"]["user"]["login"],
            ...         "url": payload["issue"]["html_url"],
            ...     })
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

    def on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Process the event with the given request.
        """
        return self._on_event(request=request, parameters=parameters)

    def fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """
        Fetch the parameter options of the trigger.
        """
        return self._fetch_parameter_options(parameter=parameter)
