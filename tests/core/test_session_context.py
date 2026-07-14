from collections.abc import Generator
from unittest.mock import MagicMock

import dify_plugin
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.core.session_context import get_current_session
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel
from dify_plugin.interfaces.model.text_embedding_model import TextEmbeddingModel


def _session(app_id: str = "app-1") -> Session:
    session = Session.empty_session()
    session.app_id = app_id
    return session


def _executor(model: object) -> PluginExecutor:
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    return PluginExecutor(config=MagicMock(), registration=registration)


def _llm_data() -> MagicMock:
    data = MagicMock()
    data.provider = "provider"
    data.model_type = "llm"
    data.model = "model"
    data.credentials = {}
    data.prompt_messages = []
    data.model_parameters = {}
    data.tools = None
    data.stop = None
    data.stream = True
    data.user_id = "user"
    return data


def _text_embedding_data() -> MagicMock:
    data = MagicMock()
    data.provider = "provider"
    data.model_type = "text-embedding"
    data.model = "model"
    data.credentials = {}
    data.texts = ["hello"]
    data.user_id = "user"
    return data


def test_get_current_session_is_public() -> None:
    assert dify_plugin.get_current_session is get_current_session
    assert "get_current_session" in dify_plugin.__all__


def test_llm_stream_keeps_session_until_consumed() -> None:
    seen: list[Session | None] = []

    def stream() -> Generator[str, None, None]:
        seen.append(get_current_session())
        yield "chunk"

    model = MagicMock(spec=LargeLanguageModel)
    model.invoke.return_value = stream()

    result = _executor(model).invoke_llm(_session(), _llm_data())

    assert get_current_session() is None
    assert list(result) == ["chunk"]
    assert seen[0] is not None
    assert seen[0].app_id == "app-1"
    assert get_current_session() is None


def test_text_embedding_exposes_session_during_invoke() -> None:
    seen: list[Session | None] = []

    def invoke(*_args: object) -> list[str]:
        seen.append(get_current_session())
        return ["embedding"]

    model = MagicMock(spec=TextEmbeddingModel)
    model.invoke.side_effect = invoke

    assert _executor(model).invoke_text_embedding(
        _session(), _text_embedding_data()
    ) == ["embedding"]
    assert seen[0] is not None
    assert seen[0].app_id == "app-1"
    assert get_current_session() is None
