from collections.abc import Mapping

from werkzeug import Request, Response

from dify_plugin.interfaces.endpoint import Endpoint


class EchoEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        return Response(
            r.get_data(),
            status=201,
            headers={"X-Item": values["item"], "X-Setting": settings["label"]},
            mimetype="application/octet-stream",
        )
