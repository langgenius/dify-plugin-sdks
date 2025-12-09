from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from werkzeug import Request, Response

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    EventDispatch,
    Subscription,
    TriggerSubscriptionConstructorRuntime,
    UnsubscribeResult,
)
from dify_plugin.interfaces.trigger import Trigger, TriggerRuntime, TriggerSubscriptionConstructor


def test_construct_trigger_provider():
    """
    Test that the TriggerProvider can be constructed without implementing any methods
    """

    class TriggerProviderImpl(Trigger):
        def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
            return EventDispatch(events=["test_event"], response=Response("OK", status=200))

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    runtime = TriggerRuntime(
        credentials={"api_key": "test_key"}, session=session, credential_type=CredentialType.API_KEY
    )

    provider = TriggerProviderImpl(runtime=runtime)
    assert provider is not None


def test_oauth_get_authorization_url():
    """
    Test that the TriggerProvider can get the authorization url
    """

    class TriggerProviderImpl(TriggerSubscriptionConstructor):
        def _validate_api_key(self, credentials: Mapping[str, Any]) -> None:
            pass

        def _create_subscription(
            self,
            endpoint: str,
            parameters: Mapping[str, Any],
            credentials: Mapping[str, Any],
            credential_type: CredentialType,
        ) -> Subscription:
            """
            Create a subscription
            """

            return Subscription(
                expires_at=1000,
                properties={},
                endpoint=endpoint,
            )

        def _delete_subscription(
            self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
        ) -> UnsubscribeResult:
            """
            Delete a subscription
            """
            return UnsubscribeResult(success=True, message="Successfully unsubscribed")

        def _refresh_subscription(
            self, subscription: Subscription, credentials: Mapping[str, Any], credential_type: CredentialType
        ) -> Subscription:
            """
            Refresh a subscription
            """
            return Subscription(expires_at=1000, properties={}, endpoint=subscription.endpoint)

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    runtime = TriggerSubscriptionConstructorRuntime(
        credentials={}, session=session, credential_type=CredentialType.UNAUTHORIZED
    )
    provider = TriggerProviderImpl(runtime=runtime)
    with pytest.raises(NotImplementedError):
        provider.oauth_get_authorization_url("http://redirect.uri", {})
