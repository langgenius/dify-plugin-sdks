import sys

from dify_plugin.core.server.__base.response_writer import ResponseWriter


class StdioResponseWriter(ResponseWriter):
    def write(self, data: str) -> None:
        sys.stdout.write(data)
        sys.stdout.flush()

    def done(self) -> None:
        pass
