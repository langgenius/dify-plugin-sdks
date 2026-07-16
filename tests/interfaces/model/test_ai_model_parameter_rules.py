from collections.abc import Mapping

from dify_plugin.entities.model import (
    PARAMETER_RULE_TEMPLATE,
    AIModelEntity,
    DefaultParameterName,
    ModelType,
)
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.ai_model import AIModel


class CustomizableAIModel(AIModel):
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
        return AIModelEntity.model_validate({
            "model": model,
            "model_type": ModelType.LLM,
            "model_properties": {},
            "parameter_rules": [{"name": "top_k", "use_template": "top_k", "min": 0}],
        })


class CustomTemplateAIModel(CustomizableAIModel):
    def get_customizable_model_schema(
        self, model: str, credentials: Mapping
    ) -> AIModelEntity:
        del credentials
        return AIModelEntity.model_validate({
            "model": model,
            "model_type": ModelType.LLM,
            "model_properties": {},
            "parameter_rules": [
                {
                    "name": "response_format",
                    "use_template": "response_format",
                    "min": 0,
                    "default": 0,
                    "precision": 0,
                    "required": False,
                }
            ],
        })

    @staticmethod
    def _get_default_parameter_rule_variable_map(
        name: DefaultParameterName,
    ) -> dict:
        return PARAMETER_RULE_TEMPLATE[name] | {
            "min": 7,
            "max": 8,
            "default": 9,
            "precision": 3,
            "required": True,
        }


def test_parameter_rule_template_preserves_explicit_zero() -> None:
    schema = CustomizableAIModel([]).get_customizable_model_schema_from_credentials(
        "test", {}
    )

    assert schema is not None
    rule = schema.parameter_rules[0]
    assert rule.min == 0
    assert rule.default == 50
    assert rule.max == 100


def test_parameter_rule_override_preserves_explicit_falsy_values() -> None:
    schema = CustomTemplateAIModel([]).get_customizable_model_schema_from_credentials(
        "test", {}
    )

    assert schema is not None
    rule = schema.parameter_rules[0]
    assert rule.min == 0
    assert rule.max == 8
    assert rule.default == 0
    assert rule.precision == 0
    assert not rule.required
