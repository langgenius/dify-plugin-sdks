from __future__ import annotations

import httpx2
import pytest
from gevent.event import Event


@pytest.fixture
def http_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[httpx2.Response], Event]:
    responses = []
    ready = Event()
    send = httpx2.Client.send

    def observe_response(
        client: httpx2.Client, request: httpx2.Request, **kwargs: object
    ) -> httpx2.Response:
        response = send(client, request, **kwargs)
        responses.append(response)
        ready.set()
        return response

    monkeypatch.setattr(httpx2.Client, "send", observe_response)
    return responses, ready
