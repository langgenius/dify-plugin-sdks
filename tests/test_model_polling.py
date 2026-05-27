from collections.abc import Generator, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import pytest
from pydantic import JsonValue, ValidationError

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


@dataclass(frozen=True)
class PollingScenario:
    user_id: str = "user-1"
    provider: str = "provider"
    model: str = "llm"
    api_key: str = "key"
    workflow_run_id: str = "wr-1"
    node_id: str = "node-1"
    job_id: str = "job-1"
    prompt_content: str = "hello"
    result_content: str = "done"
    next_check_after_seconds: int = 15
    expires_after_seconds: int = 1800
    max_attempts: int = 60

    @property
    def credentials(self) -> dict[str, str]:
        return {"api_key": self.api_key}

    @property
    def json_schema(self) -> dict[str, JsonValue]:
        return {"type": "object"}

    @property
    def plugin_state(self) -> dict[str, JsonValue]:
        return {"job_id": self.job_id}

    @property
    def daemon_prompt_messages(self) -> list[dict[str, str]]:
        return [{"role": "user", "content": self.prompt_content}]

    @property
    def prompt_messages(self) -> list[UserPromptMessage]:
        return [UserPromptMessage(content=self.prompt_content)]

    def model_entity(self) -> AIModelEntity:
        return AIModelEntity(
            model=self.model,
            label=I18nObject(en_US=self.model),
            model_type=ModelType.LLM,
            features=[ModelFeature.POLLING],
            fetch_from=FetchFrom.PREDEFINED_MODEL,
            model_properties={},
            parameter_rules=[],
        )

    def start_request(
        self,
        *,
        prompt_messages: object | None = None,
        model_parameters: dict[str, object] | None = None,
        json_schema: dict[str, JsonValue] | None = None,
        stream: bool | None = None,
    ) -> ModelStartPollingRequest:
        data: dict[str, object] = {
            "user_id": self.user_id,
            "provider": self.provider,
            "model_type": ModelType.LLM,
            "model": self.model,
            "credentials": self.credentials,
            "prompt_messages": prompt_messages or self.prompt_messages,
            "model_parameters": model_parameters or {},
            "stop": [],
            "tools": [],
            "workflow_run_id": self.workflow_run_id,
            "node_id": self.node_id,
        }
        if json_schema is not None:
            data["json_schema"] = json_schema
        if stream is not None:
            data["stream"] = stream

        return ModelStartPollingRequest(**data)

    def check_request(
        self,
        *,
        plugin_state: dict[str, JsonValue] | None = None,
    ) -> ModelCheckPollingRequest:
        data: dict[str, object] = {
            "user_id": self.user_id,
            "provider": self.provider,
            "model_type": ModelType.LLM,
            "model": self.model,
            "credentials": self.credentials,
            "workflow_run_id": self.workflow_run_id,
            "node_id": self.node_id,
            "plugin_state": plugin_state or self.plugin_state,
        }
        return ModelCheckPollingRequest(**data)

    def llm_result(self, content: str | None = None) -> LLMResult:
        return LLMResult(
            model=self.model,
            message=AssistantPromptMessage(content=content or self.result_content),
            usage=LLMUsage.empty_usage(),
        )


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

    def __init__(self, scenario: PollingScenario | None = None) -> None:
        self.scenario = scenario or PollingScenario()
        super().__init__(
            model_schemas=[self.scenario.model_entity()],
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
        return self.scenario.llm_result()

    def _start_polling(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
        user: str | None = None,
        *,
        workflow_run_id: str,
        node_id: str,
        json_schema: dict[str, JsonValue] | None = None,
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
            plugin_state=self.scenario.plugin_state,
            next_check_after_seconds=self.scenario.next_check_after_seconds,
            expires_after_seconds=self.scenario.expires_after_seconds,
            max_attempts=self.scenario.max_attempts,
        )

    def _check_polling(
        self,
        model: str,
        credentials: dict,
        plugin_state: dict[str, JsonValue],
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
            result=self.scenario.llm_result(),
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
    def __init__(self, scenario: PollingScenario | None = None) -> None:
        super().__init__(scenario)
        self.model_schemas[0].features = []


def test_polling_requests_parse_daemon_payloads() -> None:
    scenario = PollingScenario()

    start_request = scenario.start_request(
        prompt_messages=scenario.daemon_prompt_messages,
        json_schema=scenario.json_schema,
    )
    assert start_request.action == ModelActions.StartPolling
    assert start_request.stream is False
    assert isinstance(start_request.prompt_messages[0], UserPromptMessage)
    assert start_request.json_schema == scenario.json_schema

    check_request = scenario.check_request()
    assert check_request.action == ModelActions.CheckPolling
    assert check_request.plugin_state == scenario.plugin_state


def test_start_polling_request_rejects_streaming() -> None:
    scenario = PollingScenario()

    with pytest.raises(ValidationError, match="Input should be False"):
        scenario.start_request(
            prompt_messages=scenario.daemon_prompt_messages,
            stream=True,
        )


def test_check_polling_request_rejects_empty_plugin_state() -> None:
    scenario = PollingScenario()
    data: dict[str, object] = {
        "user_id": scenario.user_id,
        "provider": scenario.provider,
        "model_type": ModelType.LLM,
        "model": scenario.model,
        "credentials": scenario.credentials,
        "workflow_run_id": scenario.workflow_run_id,
        "node_id": scenario.node_id,
        "plugin_state": {},
    }

    with pytest.raises(ValidationError, match="at least 1 item"):
        ModelCheckPollingRequest(**data)


def test_executor_starts_llm_polling() -> None:
    scenario = PollingScenario()
    model = PollingLLM(scenario)
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    response = executor.start_llm_polling(
        Session.empty_session(),
        scenario.start_request(
            model_parameters={"temperature": 0.2},
            json_schema=scenario.json_schema,
        ),
    )

    assert isinstance(response, LLMPollingResult)
    assert response.status == LLMPollingStatus.RUNNING
    assert response.plugin_state == scenario.plugin_state
    assert response.next_check_after_seconds == scenario.next_check_after_seconds
    assert response.expires_after_seconds == scenario.expires_after_seconds
    assert response.max_attempts == scenario.max_attempts
    assert model.start_call is not None
    assert model.supports_polling(scenario.model, scenario.credentials)
    assert model.start_call["workflow_run_id"] == scenario.workflow_run_id
    assert model.start_call["node_id"] == scenario.node_id
    assert model.start_call["json_schema"] == scenario.json_schema
    assert model.start_call["model_parameters"] == {}


def test_executor_checks_llm_polling() -> None:
    scenario = PollingScenario()
    model = PollingLLM(scenario)
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    response = executor.check_llm_polling(
        Session.empty_session(),
        scenario.check_request(),
    )

    assert isinstance(response, LLMPollingResult)
    assert response.status == LLMPollingStatus.SUCCEEDED
    assert response.result is not None
    assert response.result.message.content == scenario.result_content
    assert model.check_call is not None
    assert model.check_call["plugin_state"] == scenario.plugin_state
    assert model.check_call["workflow_run_id"] == scenario.workflow_run_id
    assert model.check_call["node_id"] == scenario.node_id


def test_executor_rejects_llm_without_polling_feature() -> None:
    scenario = PollingScenario()
    model = NonPollingLLM(scenario)
    executor = PluginExecutor(DifyPluginEnv(), ModelRegistration(model))

    with pytest.raises(ValueError, match="does not support polling"):
        executor.start_llm_polling(
            Session.empty_session(),
            scenario.start_request(),
        )


def test_polling_result_validates_state_payloads() -> None:
    with pytest.raises(ValidationError, match="plugin_state is required"):
        LLMPollingResult(status=LLMPollingStatus.RUNNING)

    with pytest.raises(ValidationError, match="plugin_state is required"):
        LLMPollingResult(status=LLMPollingStatus.RUNNING, plugin_state={})

    with pytest.raises(ValidationError, match="result is required"):
        LLMPollingResult(status=LLMPollingStatus.SUCCEEDED)

    with pytest.raises(ValidationError, match="error is required"):
        LLMPollingResult(status=LLMPollingStatus.FAILED)


@pytest.mark.parametrize(
    "field_name",
    ["next_check_after_seconds", "expires_after_seconds", "max_attempts"],
)
def test_polling_result_rejects_non_positive_limits(field_name: str) -> None:
    scenario = PollingScenario()

    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        LLMPollingResult(
            status=LLMPollingStatus.RUNNING,
            plugin_state=scenario.plugin_state,
            **{field_name: 0},
        )
