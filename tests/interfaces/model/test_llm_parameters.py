import math
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import AIModelEntity, ModelType, ParameterRule
from dify_plugin.entities.model.llm import LLMResult, LLMUsage
from dify_plugin.entities.model.message import AssistantPromptMessage
from tests.interfaces.model.utils import StubLLM


@pytest.fixture
def llm() -> StubLLM:
    rules = [
        {
            "name": "max_tokens",
            "type": "int",
            "min": 1,
            "max": 8,
            "required": True,
            "default": 2,
        },
        {"name": "temperature", "type": "float", "min": 0, "max": 2, "precision": 2},
        {"name": "penalty", "type": "float", "min": -2, "max": 2},
        {"name": "count", "type": "float", "precision": 0},
        {"name": "enabled", "type": "boolean"},
        {"name": "mode", "type": "string", "options": ["fast", "accurate"]},
        {"name": "instructions", "type": "text"},
        {"name": "k", "use_template": "top_k", "min": 1, "max": 10},
    ]
    return StubLLM([
        AIModelEntity(
            model="model",
            model_type=ModelType.LLM,
            model_properties={},
            parameter_rules=[ParameterRule.model_validate(rule) for rule in rules],
        )
    ])


@pytest.mark.parametrize(
    "parameters",
    [
        {"max_tokens": 1},
        {"max_tokens": 8},
        {"max_tokens": True},
        {"temperature": 0},
        {"temperature": 2.0},
        {"temperature": 1.25},
        {"temperature": False},
        {"penalty": 0.125},
        {"count": 2.0},
        {"enabled": False},
        {"mode": "accurate"},
        {"instructions": ""},
    ],
)
def test_invoke_validates_and_forwards_model_parameters(
    llm: StubLLM,
    parameters: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Mock(
        return_value=LLMResult(
            model="model",
            message=AssistantPromptMessage(content="ok"),
            usage=LLMUsage.empty_usage(),
        )
    )
    monkeypatch.setattr(llm, "_invoke", provider)
    supplied = {**parameters, "unrecognized": "drop"}

    chunks = list(llm.invoke("model", {}, [], model_parameters=supplied))

    assert len(chunks) == 1
    assert chunks[0].delta.message.content == "ok"
    assert provider.call_args.kwargs["model_parameters"] == {
        "max_tokens": 2,
        **parameters,
    }
    assert supplied == {**parameters, "unrecognized": "drop"}
    assert llm.started_at == 0


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({}, {"max_tokens": 2}),
        ({"max_tokens": None, "temperature": None}, {"max_tokens": 2}),
        ({"top_k": 3}, {"max_tokens": 2, "k": 3}),
        ({"top_k": 3, "k": 4}, {"max_tokens": 2, "k": 4}),
        ({"top_k": 3, "k": None}, {"max_tokens": 2, "k": 3}),
    ],
)
def test_model_parameter_defaults_and_aliases(
    llm: StubLLM,
    parameters: dict[str, object],
    expected: dict[str, object],
) -> None:
    assert (
        llm._validate_and_filter_model_parameters("model", parameters, {}) == expected
    )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("max_tokens", 0, "greater than or equal"),
        ("max_tokens", 9, "less than or equal"),
        ("max_tokens", 1.0, "should be int"),
        ("max_tokens", "2", "should be int"),
        ("temperature", -0.01, "greater than or equal"),
        ("temperature", 2.01, "less than or equal"),
        ("temperature", "1.2", "should be float"),
        ("temperature", 1.234, "decimal places"),
        ("count", 2.5, "should be int"),
        ("enabled", 1, "should be bool"),
        ("enabled", "false", "should be bool"),
        ("mode", "unknown", "should be one of"),
        ("mode", 1, "should be string"),
        ("instructions", [], "should be string"),
        ("top_k", 11, "less than or equal"),
    ],
)
def test_invalid_model_parameters_fail_before_provider_invocation(
    llm: StubLLM,
    name: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Mock(
        return_value=LLMResult(
            model="model",
            message=AssistantPromptMessage(content="ok"),
            usage=LLMUsage.empty_usage(),
        )
    )
    monkeypatch.setattr(llm, "_invoke", provider)

    with pytest.raises(ValueError, match=message):
        list(llm.invoke("model", {}, [], model_parameters={name: value}))

    provider.assert_not_called()
    assert llm.started_at == 0


@pytest.mark.parametrize("default", [True, 0, 9])
def test_required_model_parameter_keeps_provider_default(
    llm: StubLLM, default: object
) -> None:
    llm.model_schemas[0].parameter_rules[0].default = default

    assert llm._validate_and_filter_model_parameters("model", {}, {}) == {
        "max_tokens": default
    }


def test_required_model_parameter_without_default_fails(llm: StubLLM) -> None:
    llm.model_schemas[0].parameter_rules[0].default = None

    with pytest.raises(ValueError, match="is required"):
        llm._validate_and_filter_model_parameters("model", {}, {})


def test_float_parameter_keeps_nan_acceptance(llm: StubLLM) -> None:
    parameters = llm._validate_and_filter_model_parameters(
        "model", {"penalty": float("nan")}, {}
    )
    assert math.isnan(parameters["penalty"])
