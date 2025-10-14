"""Shared utilities for Lark trigger event handlers."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Protocol, TypeVar, cast

import lark_oapi as lark
from lark_oapi.core.http import RawRequest
from werkzeug import Request

EventDataT = TypeVar("EventDataT")


class SupportsEvent(Protocol[EventDataT]):
    """Protocol for objects exposing an ``event`` attribute."""

    event: EventDataT | None


PayloadT = TypeVar("PayloadT", bound=SupportsEvent[EventDataT])


class Dispatcher(Protocol[PayloadT]):
    """Protocol describing the built dispatcher."""

    def do(self, request: RawRequest) -> None:
        """Process a raw request."""


class DispatcherBuilder(Protocol[PayloadT]):
    """Protocol describing the dispatcher builder."""

    def build(self) -> Dispatcher[PayloadT]:
        """Produce a dispatcher capable of handling requests."""


class SubscriptionWithProperties(Protocol):
    """Protocol describing a subscription that exposes properties."""

    properties: Mapping[str, str]


class RuntimeWithSubscription(Protocol):
    """Protocol describing the runtime object provided to triggers."""

    subscription: SubscriptionWithProperties


BuilderT = TypeVar("BuilderT", bound=DispatcherBuilder[PayloadT])

def build_raw_request(request: Request) -> RawRequest:
    """Construct a RawRequest from a Werkzeug request."""
    raw_request = RawRequest()
    raw_request.uri = request.url
    raw_request.headers = request.headers
    raw_request.body = request.get_data()
    return raw_request


def dispatch_single_event(
    request: Request,
    runtime: RuntimeWithSubscription,
    register_handler: Callable[[BuilderT, Callable[[PayloadT], None]], BuilderT | None],
) -> EventDataT:
    """Run the dispatcher and return the wrapped event payload."""

    event: dict[str, PayloadT] = {}

    def _capture(on_event: PayloadT) -> None:
        event["payload"] = on_event

    encrypt_key = runtime.subscription.properties.get("lark_encrypt_key", "")
    verification_token = runtime.subscription.properties.get("lark_verification_token", "")

    if not encrypt_key or not verification_token:
        raise ValueError("encrypt_key or verification_token is not set")

    builder = cast(
        BuilderT,
        lark.EventDispatcherHandler.builder(
            encrypt_key,
            verification_token,
        ),
    )
    registered_builder = register_handler(builder, _capture) or builder
    handler = registered_builder.build()
    handler.do(build_raw_request(request))

    payload = event.get("payload")
    if payload is None:
        raise ValueError("event is None")

    event_data = payload.event
    if event_data is None:
        raise ValueError("event.event is None")

    return event_data


class SupportsUserIdentity(Protocol):
    """Protocol describing the identifiers provided by user references."""

    user_id: str | None
    open_id: str | None
    union_id: str | None


def serialize_user_identity(user: SupportsUserIdentity | None) -> dict[str, str]:
    """Convert a UserId-like object into a dictionary of identifiers."""
    if user is None:
        return {"user_id": "", "open_id": "", "union_id": ""}

    return {
        "user_id": user.user_id or "",
        "open_id": user.open_id or "",
        "union_id": user.union_id or "",
    }


def serialize_user_list(users: Iterable[SupportsUserIdentity | None]) -> list[dict[str, str]]:
    """Convert an iterable of UserId-like objects into serialisable dictionaries."""
    return [serialize_user_identity(user) for user in users if user is not None]


