import json
from collections.abc import Mapping
from typing import Optional

from werkzeug import Request, Response

from dify_plugin import Endpoint


class GirlsTalk(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """

        app: Optional[dict] = settings.get("app")
        if not app:
            return Response("App is required", status=400)

        data = r.get_json()
        query = data.get("query")
        conversation_id = data.get("conversation_id")

        if not query:
            return Response("Query is required", status=400)

        def generator():
            response = self.session.app.chat.invoke(
                app_id=app.get("app_id"),
                query=query,
                inputs={},
                conversation_id=conversation_id,
                response_mode="streaming",
            )

            for chunk in response:
                yield json.dumps(chunk) + "\n\n"

        return Response(generator(), status=200, content_type="text/event-stream")
