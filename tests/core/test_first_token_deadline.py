import socket
import time
from collections.abc import Generator
from unittest.mock import MagicMock

import gevent
import pytest
import requests

from dify_plugin.core import first_token_deadline
from dify_plugin.core.entities.plugin.request import ModelInvokeLLMRequest
from dify_plugin.core.first_token_deadline import guard_first_token
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.errors.model import FirstTokenTimeoutError, InvokeError
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel

BUDGET = 0.2
TOLERANCE = 0.6


def slow_before_first_yield(delay: float) -> Generator[str, None, None]:
    """A provider that issues its request eagerly, before yielding anything."""
    gevent.sleep(delay)
    yield "first"
    yield "second"


def slow_between_yields(delay: float) -> Generator[str, None, None]:
    yield "first"
    gevent.sleep(delay)
    yield "second"


def test_a_stall_before_the_first_chunk_is_cut_at_the_budget() -> None:
    started = time.monotonic()

    with pytest.raises(FirstTokenTimeoutError):
        list(guard_first_token(slow_before_first_yield(10), BUDGET))

    assert time.monotonic() - started < TOLERANCE


def test_the_budget_does_not_bound_the_gap_between_later_chunks() -> None:
    """Strictly first-token-only: the scope is dropped once a chunk arrives."""
    chunks = list(guard_first_token(slow_between_yields(BUDGET * 3), BUDGET))

    assert chunks == ["first", "second"]


def test_a_prompt_stream_is_passed_through_untouched() -> None:
    assert list(guard_first_token(slow_before_first_yield(0), BUDGET)) == [
        "first",
        "second",
    ]


def test_an_empty_stream_ends_cleanly() -> None:
    def nothing() -> Generator[str, None, None]:
        return
        yield

    assert list(guard_first_token(nothing(), BUDGET)) == []


@pytest.mark.parametrize("budget", [None, 0, 0.0, -1])
def test_a_non_positive_budget_leaves_the_stream_unguarded(
    budget: float | None,
) -> None:
    assert list(guard_first_token(slow_before_first_yield(0), budget)) == [
        "first",
        "second",
    ]


def test_an_outer_timeout_is_not_reported_as_a_first_token_timeout() -> None:
    """Identity check: only our own Timeout may become a FirstTokenTimeoutError."""
    outer = gevent.Timeout(BUDGET)
    outer.start()
    try:
        with pytest.raises(gevent.Timeout) as caught:
            list(guard_first_token(slow_before_first_yield(10), BUDGET * 10))
        assert caught.value is outer
    finally:
        outer.close()


def test_the_budget_is_ignored_when_a_blocking_read_cannot_be_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail open: no enforcement is correct, killing a healthy request is not."""
    monkeypatch.setattr(first_token_deadline, "interruptible", lambda: False)

    assert list(guard_first_token(slow_before_first_yield(0), BUDGET)) == [
        "first",
        "second",
    ]


def test_the_error_is_an_invoke_error_whose_name_is_the_wire_contract() -> None:
    """`error_type` is `type(e).__name__`, so the class name is protocol."""
    error = FirstTokenTimeoutError("nope")

    assert isinstance(error, InvokeError)
    assert type(error).__name__ == "FirstTokenTimeoutError"
    assert error.description == "nope"


def serve_and_stall(*, send_headers: bool) -> tuple[str, socket.socket]:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def serve() -> None:
        conn, _ = listener.accept()
        conn.recv(65536)
        if send_headers:
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
            )
        gevent.sleep(10)
        conn.close()

    gevent.spawn(serve)
    return f"http://127.0.0.1:{listener.getsockname()[1]}/", listener


@pytest.mark.parametrize("send_headers", [False, True])
def test_a_real_blocked_socket_read_is_cut_and_the_connection_released(
    send_headers: bool,
) -> None:
    """The pre-header case is the one a guard placed after the request would miss."""
    url, listener = serve_and_stall(send_headers=send_headers)
    responses: list[requests.Response] = []

    def provider() -> Generator[bytes, None, None]:
        response = requests.get(url, stream=True, timeout=30)
        responses.append(response)
        yield from response.iter_lines()

    started = time.monotonic()
    try:
        with pytest.raises(FirstTokenTimeoutError):
            list(guard_first_token(provider(), BUDGET))
        assert time.monotonic() - started < TOLERANCE
        if responses:
            assert responses[0].raw._fp.fp is None
    finally:
        listener.close()


def build_request(**overrides: object) -> ModelInvokeLLMRequest:
    payload: dict[str, object] = {
        "type": "model",
        "user_id": "u",
        "provider": "p",
        "model_type": "llm",
        "model": "m",
        "credentials": {},
        "prompt_messages": [],
        "model_parameters": {},
        "stop": None,
        "tools": None,
    }
    payload.update(overrides)
    return ModelInvokeLLMRequest(**payload)


def test_an_old_daemon_that_omits_the_budget_still_parses() -> None:
    assert build_request().first_token_timeout is None


def test_the_budget_is_read_off_the_request_in_seconds() -> None:
    assert build_request(first_token_timeout=1.5).first_token_timeout == pytest.approx(
        1.5
    )


def test_a_non_streaming_invocation_has_no_first_token_budget() -> None:
    """Without a stream the single result arrives when generation is done, so the
    budget would stop being about the first token."""
    assert build_request(first_token_timeout=1.5).first_token_budget == pytest.approx(
        1.5
    )
    assert (
        build_request(first_token_timeout=1.5, stream=False).first_token_budget is None
    )


def test_a_field_a_newer_caller_adds_is_ignored_rather_than_rejected() -> None:
    """Tolerant reader: a newer caller must not be able to break an older plugin."""
    assert build_request(some_future_field={"a": 1}).first_token_timeout is None


def test_the_executor_arms_the_budget_carried_on_the_request() -> None:
    """The wire this feature is inert without."""
    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.return_value = slow_before_first_yield(10)
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    executor = PluginExecutor(config=MagicMock(), registration=registration)

    data = build_request(first_token_timeout=BUDGET)
    started = time.monotonic()

    with pytest.raises(FirstTokenTimeoutError):
        list(executor.invoke_llm(Session.empty_session(), data))

    assert time.monotonic() - started < TOLERANCE


def test_the_executor_leaves_a_stream_unguarded_when_no_budget_is_carried() -> None:
    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.return_value = slow_before_first_yield(0)
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    executor = PluginExecutor(config=MagicMock(), registration=registration)

    chunks = list(executor.invoke_llm(Session.empty_session(), build_request()))

    assert chunks == ["first", "second"]
