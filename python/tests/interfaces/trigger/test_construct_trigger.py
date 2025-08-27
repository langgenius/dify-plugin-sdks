from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.trigger import TriggerEvent, TriggerRuntime
from dify_plugin.interfaces.trigger import Trigger


def test_construct_trigger():
    """
    Test the constructor of Trigger

    NOTE:
    - This test is to ensure that the constructor of Trigger is not overridden.
    - And ensure a breaking change will be detected by CI.
    """

    class TriggerImpl(Trigger):
        def _trigger(self, request: Request, values: Mapping, parameters: Mapping) -> TriggerEvent:
            return TriggerEvent(variables={})

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )

    trigger = TriggerImpl(runtime=TriggerRuntime(credentials={}, session_id="test"), session=session)
    assert trigger is not None
