import os
from collections.abc import Mapping

from werkzeug import Request, Response

from shai_plugin import Endpoint


class NekoEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        # read file from girls.html using current python file relative path
        with open(os.path.join(os.path.dirname(__file__), "girls.html")) as f:
            return Response(
                f.read().replace("{{ bot_name }}", settings.get("bot_name", "Candy")),
                status=200,
                content_type="text/html",
            )
