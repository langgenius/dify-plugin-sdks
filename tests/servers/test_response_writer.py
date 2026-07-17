from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter


class RecordingResponseWriter(StdioResponseWriter):
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, data: str) -> None:
        self.writes.append(data)

    def done(self) -> None:
        pass


def test_response_writer_preserves_standalone_frame_delimiter() -> None:
    writer = RecordingResponseWriter()

    writer.log({})

    assert len(writer.writes) == 2
    assert writer.writes[1] == "\n\n"
