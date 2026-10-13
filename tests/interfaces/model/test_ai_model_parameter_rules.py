from collections.abc import Mapping
from typing import ClassVar
from unittest.mock import Mock

import pytest
from pydantic import ConfigDict

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    PARAMETER_RULE_TEMPLATE,
    AIModelEntity,
    DefaultParameterName,
    ModelType,
    ParameterRule,
    ParameterType,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.ai_model import AIModel


class PostInitParameterRule(ParameterRule):
    calls: ClassVar[int] = 0

    def model_post_init(self, context: object) -> None:
        del context
        type(self).calls += 1
        assert self.type is ParameterType.INT


class FrozenParameterRule(ParameterRule):
    model_config = ConfigDict(frozen=True)


class CustomTemplateAIModel(AIModel):
    model_type = ModelType.LLM

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def get_customizable_model_schema(
        self, model: str, credentials: Mapping
    ) -> AIModelEntity:
        del credentials
        if model == "frozen":
            rule = FrozenParameterRule.model_validate({
                "name": "top_k",
                "use_template": "top_k",
            })
        elif model == "late":
            rule = ParameterRule(
                name="top_k",
                label=I18nObject(en_us="Top K"),
                type=ParameterType.INT,
            )
            rule.use_template = "top_k"
        else:
            rule = ParameterRule.model_validate({
                "name": "top_k",
                "use_template": "top_k",
            }).model_copy(update={"max": 7})
        return AIModelEntity.model_validate({
            "model": model,
            "model_type": ModelType.LLM,
            "model_properties": {},
            "parameter_rules": [rule],
        })

    @staticmethod
    def _get_default_parameter_rule_variable_map(
        name: DefaultParameterName,
    ) -> dict:
        return PARAMETER_RULE_TEMPLATE[name] | {"max": 8}


def test_parameter_rule_runs_subclass_post_init_once() -> None:
    PostInitParameterRule.calls = 0

    rule = PostInitParameterRule.model_validate({
        "name": "top_k",
        "use_template": "top_k",
    })

    assert PostInitParameterRule.calls == 1
    assert rule == PostInitParameterRule.model_validate(rule.model_dump())


def test_parameter_rule_expands_late_template() -> None:
    schema = CustomTemplateAIModel([]).get_customizable_model_schema_from_credentials(
        "late", {}
    )

    assert schema is not None
    assert schema.parameter_rules[0].max == 8


def test_parameter_rule_preserves_model_copy_update() -> None:
    schema = CustomTemplateAIModel([]).get_customizable_model_schema_from_credentials(
        "copy", {}
    )

    assert schema is not None
    assert schema.parameter_rules[0].max == 7


def test_custom_model_schema_preserves_provider_zero_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = CustomTemplateAIModel([])
    schema = AIModelEntity(
        model="custom",
        model_type=ModelType.LLM,
        model_properties={},
        parameter_rules=[
            ParameterRule.model_validate({
                "name": "top_p",
                "use_template": "top_p",
                "min": 0,
                "max": 0,
                "default": 0,
                "precision": 0,
            })
        ],
    )
    monkeypatch.setattr(
        model, "get_customizable_model_schema", Mock(return_value=schema)
    )

    result = model.get_model_schema("custom", {"api_key": "key"})

    assert result is not None
    rule = result.parameter_rules[0]
    assert (rule.min, rule.max, rule.default, rule.precision) == (0, 0, 0, 0)


def test_custom_model_schema_fills_missing_template_translations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = CustomTemplateAIModel([])
    schema = model.get_customizable_model_schema("copy", {})
    schema.parameter_rules[0].help = I18nObject(en_us="", zh_hans="")
    monkeypatch.setattr(
        model, "get_customizable_model_schema", Mock(return_value=schema)
    )

    result = model.get_model_schema("copy", {"api_key": "key"})

    assert result is not None
    help_text = result.parameter_rules[0].help
    template_help = PARAMETER_RULE_TEMPLATE[DefaultParameterName.TOP_K]["help"]
    assert help_text is not None
    assert help_text.en_us == template_help["en_US"]
    assert help_text.zh_hans == template_help["zh_Hans"]


def test_parameter_rule_template_keeps_legacy_value_error_boundary() -> None:
    schema = CustomTemplateAIModel([]).get_customizable_model_schema_from_credentials(
        "frozen", {}
    )

    assert schema is not None
    assert isinstance(schema.parameter_rules[0], FrozenParameterRule)
    assert schema.parameter_rules[0].precision == 0
