from collections.abc import Generator, Mapping
from typing import Any

import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.request import (
    ModelActions,
    ModelCheckPollingRequest,
    ModelStartPollingRequest,
)
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import AIModelEntity, FetchFrom, ModelFeature, ModelType
from dify_plugin.entities.model.llm import (
    LLMPollingResult,
    LLMPollingStatus,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
    UserPromptMessage,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel


class ModelRegistration:
    def __init__(self, model_instance: LargeLanguageModel) -> None:
        self.model_instance = model_instance
        self.provider: str | None = None
        self.model_type: ModelType | None = None

    def get_model_instance(
        self,
        provider: str,
        model_type: ModelType,
    ) -> LargeLanguageModel:
        self.provider = provider
        self.model_type = model_type
        return self.model_instance


class PollingLLM(LargeLanguageModel):
    model_type = ModelType.LLM

    def __init__(self) -> None:
        super().__init__(
            model_schemas=[
                AIModelEntity(
                    model="llm",
                    label=I18nObject(en_us="llm"),
                    model_type=ModelType.LLM,
                    features=[ModelFeature.POLLING],
                    fetch_from=FetchFrom.PREDEFINED_MODEL,
                    model_properties={},
                    parameter_rules=[],
                ),
            ],
        )
        self.start_call: dict[str, Any] | None = None
        self.check_call: dict[str, Any] | None = None

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        del (
            model,
            credentials,
            prompt_messages,
            model_parameters,
            tools,
            stop,
            stream,
            user,
        )
        return _llm_result("done")

    def _start_polling(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        user: str | None = None,
        *,
        workflow_run_id: str,
        node_id: str,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMPollingResult:
        self.start_call = {
            "model": model,
            "credentials": credentials,
            "prompt_messages": prompt_messages,
            "model_parameters": model_parameters,
            "tools": tools,
            "stop": stop,
            "stream": stream,
            "user": user,
            "workflow_run_id": workflow_run_id,
            "node_id": node_id,
            "json_schema": json_schema,
        }
        return LLMPollingResult(
            status=LLMPollingStatus.RUNNING,
            plugin_state={"job_id": "job-1"},
            next_check_after_seconds=15,
            expires_after_seconds=1800,
            max_attempts=60,
        )

    def _check_polling(
        self,
        model: str,
        credentials: dict,
        plugin_state: dict[str, Any],
        user: str | None = None,
        *,
        workflow_run_id: str,
        node_id: str,
    ) -> LLMPollingResult:
        self.check_call = {
            "model": model,
            "credentials": credentials,
            "plugin_state": plugin_state,
            "user": user,
            "workflow_run_id": workflow_run_id,
            "node_id": node_id,
        }
        return LLMPollingResult(
            status=LLMPollingStatus.SUCCEEDED,
            result=_llm_result("done"),
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        del model, credentials, prompt_messages, tools
        return 0


class NonPollingLLM(PollingLLM):
    def __init__(self) -> None:
        super().__init__()
        self.model_schemas[0].features = []


def test_polling_requests_parse_daemon_payloads() -> None:
    start_request = ModelStartPollingRequest(
        user_id="user-1",
        provider="provider",
        model_type=ModelType.LLM,
        model="llm",
        credentials={"api_key": "key"},
        prompt_messages=[{"role": "user", "content": "hello"}],
        model_parameters={},
        stop=[],
        tools=[],
        json_schema={"type": "object"},
        workflow_run_id="wr-1",
        node_id="node-1",
    )
    assert start_request.action == ModelActions.StartPolling
    assert start_request.stream is False
    assert isinstance(start_request.prompt_messages[0], UserPromptMessage)
    assert start_request.json_schema == {"type": "object"}

    check_request = ModelCheckPollingRequest(
        user_id="user-1",
        provider="provider",
        model_type=ModelType.LLM,
        model="llm",
        credentials={"api_key": "key"},
        workflow_run_id="wr-1",
        node_id="node-1",
        plugin_state={"job_id": "job-1"},
    )
    assert check_request.action == ModelActions.CheckPolling
    assert check_request.plugin_state == {"job_id": "job-1"}


def test_executor_starts_llm_polling() -> None:
    model = PollingLLM()
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    response = executor.start_llm_polling(
        Session.empty_session(),
        ModelStartPollingRequest(
            user_id="user-1",
            provider="provider",
            model_type=ModelType.LLM,
            model="llm",
            credentials={"api_key": "key"},
            prompt_messages=[UserPromptMessage(content="hello")],
            model_parameters={"temperature": 0.2},
            stop=[],
            tools=[],
            json_schema={"type": "object"},
            workflow_run_id="wr-1",
            node_id="node-1",
        ),
    )

    assert isinstance(response, LLMPollingResult)
    assert response.status == LLMPollingStatus.RUNNING
    assert response.plugin_state == {"job_id": "job-1"}
    assert response.next_check_after_seconds == 15
    assert response.expires_after_seconds == 1800
    assert response.max_attempts == 60
    assert model.start_call is not None
    assert model.supports_polling("llm", {"api_key": "key"})
    assert model.start_call["workflow_run_id"] == "wr-1"
    assert model.start_call["node_id"] == "node-1"
    assert model.start_call["json_schema"] == {"type": "object"}
    assert model.start_call["model_parameters"] == {}


def test_executor_checks_llm_polling() -> None:
    model = PollingLLM()
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    response = executor.check_llm_polling(
        Session.empty_session(),
        ModelCheckPollingRequest(
            user_id="user-1",
            provider="provider",
            model_type=ModelType.LLM,
            model="llm",
            credentials={"api_key": "key"},
            workflow_run_id="wr-1",
            node_id="node-1",
            plugin_state={"job_id": "job-1"},
        ),
    )

    assert isinstance(response, LLMPollingResult)
    assert response.status == LLMPollingStatus.SUCCEEDED
    assert response.result is not None
    assert response.result.message.content == "done"
    assert model.check_call is not None
    assert model.check_call["plugin_state"] == {"job_id": "job-1"}
    assert model.check_call["workflow_run_id"] == "wr-1"
    assert model.check_call["node_id"] == "node-1"


def test_executor_rejects_llm_without_polling_feature() -> None:
    model = NonPollingLLM()
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    with pytest.raises(ValueError, match="does not support polling"):
        executor.start_llm_polling(
            Session.empty_session(),
            ModelStartPollingRequest(
                user_id="user-1",
                provider="provider",
                model_type=ModelType.LLM,
                model="llm",
                credentials={"api_key": "key"},
                prompt_messages=[UserPromptMessage(content="hello")],
                model_parameters={},
                stop=[],
                tools=[],
                workflow_run_id="wr-1",
                node_id="node-1",
            ),
        )


def test_polling_result_validates_state_payloads() -> None:
    with pytest.raises(ValueError, match="plugin_state is required"):
        LLMPollingResult(status=LLMPollingStatus.RUNNING)

    with pytest.raises(ValueError, match="result is required"):
        LLMPollingResult(status=LLMPollingStatus.SUCCEEDED)

    with pytest.raises(ValueError, match="error is required"):
        LLMPollingResult(status=LLMPollingStatus.FAILED)


@pytest.mark.parametrize(
    "field_name",
    ["next_check_after_seconds", "expires_after_seconds", "max_attempts"],
)
def test_polling_result_rejects_non_positive_limits(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be greater than 0"):
        LLMPollingResult(
            status=LLMPollingStatus.RUNNING,
            plugin_state={"job_id": "job-1"},
            **{field_name: 0},
        )


def _llm_result(content: str) -> LLMResult:
    return LLMResult(
        model="llm",
        message=AssistantPromptMessage(content=content),
        usage=LLMUsage.empty_usage(),
    )
