from collections.abc import Mapping
from typing import Optional

from werkzeug import Request, Response

from dify_plugin import Endpoint
from dify_plugin.entities.model.tts import TTSModelConfig


class Tts(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """
        content_text = r.get_json().get("content_text")

        tts_model: Optional[dict] = settings.get("tts_model")
        if not tts_model:
            return Response("tts_model is required", status=400)

        response = self.session.model.tts.invoke(
            model_config=TTSModelConfig(**tts_model),
            content_text=content_text,
        )

        def generator():
            yield from response

        return Response(generator(), status=200, content_type="text/event-stream")
