"""Shared utilities for Lark trigger event handlers."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

import lark_oapi as lark
from lark_oapi.core.http import RawRequest
from werkzeug import Request


def build_raw_request(request: Request) -> RawRequest:
    """Construct a RawRequest from a Werkzeug request."""
    raw_request = RawRequest()
    raw_request.uri = request.url
    raw_request.headers = request.headers
    raw_request.body = request.get_data()
    return raw_request


def dispatch_single_event(
    request: Request,
    runtime: Any,
    register_handler: Callable[[Any, Callable[[Any], None]], Any],
) -> Any:
    """Run the dispatcher and return the wrapped event payload."""

    event: dict[str, Any] = {}

    def _capture(on_event: Any) -> None:
        event["payload"] = on_event

    encrypt_key = runtime.subscription.properties.get("lark_encrypt_key", "")
    verification_token = runtime.subscription.properties.get("lark_verification_token", "")

    if not encrypt_key or not verification_token:
        raise ValueError("encrypt_key or verification_token is not set")

    builder = lark.EventDispatcherHandler.builder(
        encrypt_key,
        verification_token,
    )
    registered_builder = register_handler(builder, _capture) or builder
    handler = registered_builder.build()
    handler.do(build_raw_request(request))

    payload = event.get("payload")
    if payload is None:
        raise ValueError("event is None")

    event_data = getattr(payload, "event", None)
    if event_data is None:
        raise ValueError("event.event is None")

    return event_data


def serialize_user_identity(user: Any) -> dict[str, str]:
    """Convert a UserId-like object into a dictionary of identifiers."""
    if user is None:
        return {"user_id": "", "open_id": "", "union_id": ""}

    return {
        "user_id": getattr(user, "user_id", "") or "",
        "open_id": getattr(user, "open_id", "") or "",
        "union_id": getattr(user, "union_id", "") or "",
    }


def serialize_user_list(users: Iterable[Any]) -> list[dict[str, str]]:
    """Convert an iterable of UserId-like objects into serialisable dictionaries."""
    return [serialize_user_identity(user) for user in users if user is not None]


def dumps_json(data: Any) -> str:
    """Serialize data to JSON with UTF-8 support."""
    return json.dumps(data, ensure_ascii=False)
