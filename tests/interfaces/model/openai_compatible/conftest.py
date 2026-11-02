from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from gevent.event import Event

from dify_plugin.interfaces.model.openai_compatible import llm

if TYPE_CHECKING:
    from requests import Response


@pytest.fixture
def http_responses(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Response], Event]:
    responses = []
    ready = Event()
    post = llm.http.post

    def observe_response(url: str, **kwargs: object) -> Response:
        response = post(url, **kwargs)
        responses.append(response)
        ready.set()
        return response

    monkeypatch.setattr(llm.http, "post", observe_response)
    return responses, ready
