from queue import Queue

from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader


def test_serverless_response_stops_after_sentinel() -> None:
    reader = object.__new__(ServerlessRequestReader)
    queue = Queue[str | None]()
    queue.put("chunk")
    queue.put(None)

    assert list(reader._generate_response(queue)) == ["chunk"]
