from collections.abc import Mapping
from pathlib import Path

from werkzeug import Request, Response

from dify_plugin import Endpoint


class NekoEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # read file from girls.html using current python file relative path
        html = (Path(__file__).parent / "girls.html").read_text()
        return Response(
            html.replace("{{ bot_name }}", settings.get("bot_name", "Candy")),
            status=200,
            content_type="text/html",
        )
