from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import Subscription, Variables
from dify_plugin.interfaces.trigger import Event, EventRuntime


def test_construct_trigger():
    """
    Test the constructor of Event

    NOTE:
    - This test is to ensure that the constructor of Event is not overridden.
    - And ensure a breaking change will be detected by CI.
    """

    class TriggerEventImpl(Event):
        def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
            return Variables(variables={})

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    trigger = TriggerEventImpl(
        runtime=EventRuntime(
            session=session,
            credential_type=CredentialType.UNAUTHORIZED,
            subscription=Subscription(expires_at=0, endpoint="test", parameters={}, properties={}),
            credentials={},
        )
    )
    assert trigger is not None
