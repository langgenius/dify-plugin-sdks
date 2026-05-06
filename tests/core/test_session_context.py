"""Tests for dify_plugin.core.session_context — ContextVar-based session propagation.

Best practices applied:
- Each test cleans up ContextVar state via an autouse fixture.
- ContextVar tests and plugin_executor integration tests are separated.
- Thread isolation is verified with ThreadPoolExecutor.
"""

from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from dify_plugin.core.runtime import Session
from dify_plugin.core.session_context import (
    _current_session,  # noqa: PLC2701
    get_current_session,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_context_var() -> None:
    """Ensure _current_session is None before and after every test."""
    # Reset to default before the test
    token = _current_session.set(None)  # type: ignore[arg-type]
    _current_session.reset(token)
    yield  # type: ignore[misc]
    # Reset to default after the test (in case a test forgot to clean up)
    with contextlib.suppress(ValueError):
        _current_session.set(None)  # type: ignore[arg-type]


def _make_session(app_id: str | None = "app-test-123") -> Session:
    """Create a minimal Session with the given app_id."""
    return Session(
        session_id="sess-1",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=MagicMock(),
        writer=MagicMock(),
        app_id=app_id,
    )


# ---------------------------------------------------------------------------
# 1. get_current_session() — basic ContextVar behaviour
# ---------------------------------------------------------------------------


class TestGetCurrentSessionBasic:
    """Verify the raw ContextVar get/set/reset semantics."""

    def test_returns_none_by_default(self) -> None:
        assert get_current_session() is None

    def test_returns_session_after_set(self) -> None:
        session = _make_session()
        token = _current_session.set(session)
        try:
            assert get_current_session() is session
        finally:
            _current_session.reset(token)

    def test_returns_none_after_reset(self) -> None:
        session = _make_session()
        token = _current_session.set(session)
        _current_session.reset(token)
        assert get_current_session() is None

    def test_nested_set_restores_previous_on_reset(self) -> None:
        """ContextVar spec: reset restores the value before the corresponding set."""
        session_a = _make_session(app_id="app-a")
        session_b = _make_session(app_id="app-b")

        token_a = _current_session.set(session_a)
        token_b = _current_session.set(session_b)

        assert get_current_session() is session_b

        _current_session.reset(token_b)
        assert get_current_session() is session_a

        _current_session.reset(token_a)
        assert get_current_session() is None

    def test_thread_isolation(self) -> None:
        """A session set in the main thread must not be visible in a worker thread."""
        session = _make_session()
        token = _current_session.set(session)

        results: list[Session | None] = []

        def _worker() -> None:
            results.append(get_current_session())

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_worker).result()

        _current_session.reset(token)
        assert results == [None]


# ---------------------------------------------------------------------------
# 2. app_id access through the session
# ---------------------------------------------------------------------------


class TestAppIdAccess:
    def test_app_id_is_accessible(self) -> None:
        session = _make_session(app_id="app-456")
        token = _current_session.set(session)
        try:
            current = get_current_session()
            assert current is not None
            assert current.app_id == "app-456"
        finally:
            _current_session.reset(token)

    def test_app_id_none_for_out_of_app_context(self) -> None:
        session = _make_session(app_id=None)
        token = _current_session.set(session)
        try:
            current = get_current_session()
            assert current is not None
            assert current.app_id is None
        finally:
            _current_session.reset(token)


# ---------------------------------------------------------------------------
# 3. plugin_executor integration
#
# Instead of instantiating real LargeLanguageModel subclasses (which pull in
# graphon and require complex setup), we directly test that the ContextVar
# is set/reset around the model invocation by patching the model instance.
# ---------------------------------------------------------------------------


class TestPluginExecutorSessionPropagation:
    """Verify plugin_executor.invoke_llm sets/resets the ContextVar."""

    @staticmethod
    def _make_executor_with_mock_llm(
        invoke_side_effect: object = None,
    ) -> tuple[object, MagicMock]:
        """Return (executor, mock_model) with mock_model passing isinstance checks."""
        from dify_plugin.core.plugin_executor import PluginExecutor
        from dify_plugin.interfaces.model.large_language_model import (
            LargeLanguageModel,
        )

        mock_model = MagicMock(spec=LargeLanguageModel)
        if invoke_side_effect is not None:
            mock_model.invoke.side_effect = invoke_side_effect
        else:
            mock_model.invoke.return_value = iter([])

        config = MagicMock()
        registration = MagicMock()
        registration.get_model_instance.return_value = mock_model

        executor = PluginExecutor(config=config, registration=registration)
        return executor, mock_model

    @staticmethod
    def _make_llm_data() -> MagicMock:
        data = MagicMock()
        data.provider = "test-provider"
        data.model_type = "llm"
        data.model = "gpt-test"
        data.credentials = {}
        data.prompt_messages = []
        data.model_parameters = {}
        data.tools = None
        data.stop = None
        data.stream = False
        data.user_id = "user-1"
        return data

    def test_session_is_set_during_invoke(self) -> None:
        """get_current_session() returns the session while invoke is running."""
        captured: list[Session | None] = []

        def _capture_invoke(*_a: object, **_kw: object) -> list:
            captured.append(get_current_session())
            return iter([])  # type: ignore[return-value]

        executor, _ = self._make_executor_with_mock_llm(
            invoke_side_effect=_capture_invoke,
        )
        session = _make_session(app_id="app-during")
        data = self._make_llm_data()

        result = executor.invoke_llm(session, data)
        if hasattr(result, "__iter__") and not isinstance(result, str | bytes):
            list(result)

        assert len(captured) == 1
        assert captured[0] is session
        assert captured[0].app_id == "app-during"

    def test_session_is_reset_after_invoke(self) -> None:
        """After invoke_llm returns, get_current_session() is None."""
        executor, _ = self._make_executor_with_mock_llm()
        session = _make_session(app_id="app-after")
        data = self._make_llm_data()

        result = executor.invoke_llm(session, data)
        if hasattr(result, "__iter__") and not isinstance(result, str | bytes):
            list(result)

        assert get_current_session() is None

    def test_session_is_reset_on_exception(self) -> None:
        """If invoke raises during iteration, the ContextVar is still cleaned up."""
        executor, _ = self._make_executor_with_mock_llm(
            invoke_side_effect=RuntimeError("boom"),
        )
        session = _make_session(app_id="app-error")
        data = self._make_llm_data()

        result = executor.invoke_llm(session, data)
        # Exception occurs when the generator is consumed
        with pytest.raises(RuntimeError, match="boom"):
            list(result)

        assert get_current_session() is None


# ---------------------------------------------------------------------------
# 4. Public API surface
# ---------------------------------------------------------------------------


class TestPublicApi:
    def test_importable_from_top_level(self) -> None:
        from dify_plugin import get_current_session as fn

        assert callable(fn)

    def test_listed_in_all(self) -> None:
        import dify_plugin

        assert "get_current_session" in dify_plugin.__all__
