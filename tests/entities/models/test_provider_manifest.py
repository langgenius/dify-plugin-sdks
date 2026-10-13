from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.provider import ModelProviderConfiguration
from tests.core.plugin_fixtures import contract_source

__all__ = ["contract_source"]


@pytest.mark.parametrize("existing_position", [False, True])
def test_model_glob_loads_position_separately_from_models(
    contract_source: Path, existing_position: bool
) -> None:
    # OpenAI's predefined glob includes _position.yaml alongside model declarations.
    data = yaml.safe_load((contract_source / "models/provider.yaml").read_text())
    data["models"]["llm"]["predefined"] = ["models/llm.yaml", "models/_position.yaml"]
    (contract_source / "models/_position.yaml").write_text("- echo\n")
    if existing_position:
        data["position"] = {"tts": ["voice"]}

    provider = ModelProviderConfiguration.model_validate(data)

    assert len(provider.models) == 6
    assert [
        item.model for item in provider.models if item.model_type == ModelType.LLM
    ] == ["echo"]
    assert provider.position.llm == ["echo"]
    assert provider.position.tts == (["voice"] if existing_position else [])


@pytest.mark.parametrize("models", [[], "models/*.yaml"])
def test_model_provider_rejects_invalid_glob_mapping(
    contract_source: Path, models: object
) -> None:
    data = yaml.safe_load((contract_source / "models/provider.yaml").read_text())
    data["models"] = models

    with pytest.raises((TypeError, ValidationError), match="models"):
        ModelProviderConfiguration.model_validate(data)


def test_model_provider_reports_empty_matched_file(contract_source: Path) -> None:
    data = yaml.safe_load((contract_source / "models/provider.yaml").read_text())
    data["models"]["llm"]["predefined"] = ["models/empty.yaml"]
    (contract_source / "models/empty.yaml").write_text("")

    with pytest.raises(
        ValidationError, match=r"Error loading model entity:.*empty\.yaml"
    ):
        ModelProviderConfiguration.model_validate(data)


def test_model_provider_manifest_can_be_reused_without_losing_globs(
    contract_source: Path,
) -> None:
    data = yaml.safe_load((contract_source / "models/provider.yaml").read_text())
    first = ModelProviderConfiguration.model_validate(data)
    second = ModelProviderConfiguration.model_validate(data)

    assert first == second
