from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug import Request, Response

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.trigger import Subscription, TriggerDispatch, TriggerSubscriptionConstructorRuntime
from dify_plugin.interfaces.trigger import TriggerProvider, TriggerSubscriptionConstructor


def test_construct_trigger_provider():
    """
    Test that the TriggerProvider can be constructed without implementing any methods
    """

    class TriggerProviderImpl(TriggerProvider):
        def _dispatch_event(self, subscription: Subscription, request: Request) -> TriggerDispatch:
            return TriggerDispatch(triggers=["test_event"], response=Response("OK", status=200))

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    provider = TriggerProviderImpl(session=session)
    assert provider is not None


def test_oauth_get_authorization_url():
    """
    Test that the TriggerProvider can get the authorization url
    """

    class TriggerProviderImpl(TriggerSubscriptionConstructor):
        def _validate_api_key(self, credentials: dict):
            return True

        def _create_subscription(
            self, endpoint: str, credentials: dict, selected_events: list[str], parameters: dict
        ) -> Subscription:
            """
            Create a subscription
            """
            return Subscription(
                expires_at=1000,
                properties={},
                endpoint=endpoint,
                credentials=credentials,
                subscribed_events=selected_events,
            )

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    runtime = TriggerSubscriptionConstructorRuntime(credentials={}, session_id="test")
    provider = TriggerProviderImpl(session=session, runtime=runtime)
    with pytest.raises(NotImplementedError):
        provider.oauth_get_authorization_url("http://redirect.uri", {})
