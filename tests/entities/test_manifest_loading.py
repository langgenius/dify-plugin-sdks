from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from dify_plugin.entities.agent import AgentStrategyProviderConfiguration
from dify_plugin.entities.datasource_manifest import DatasourceProviderManifest
from dify_plugin.entities.endpoint import EndpointProviderConfiguration
from dify_plugin.entities.tool import ToolProviderConfiguration
from dify_plugin.entities.trigger import TriggerProviderConfiguration
from tests.core.plugin_fixtures import contract_source

__all__ = ["contract_source"]


@pytest.fixture(
    params=[
        pytest.param(
            (ToolProviderConfiguration, "provider/contract.yaml", "tools"), id="tool"
        ),
        pytest.param(
            (AgentStrategyProviderConfiguration, "agents/provider.yaml", "strategies"),
            id="agent",
        ),
        pytest.param(
            (DatasourceProviderManifest, "datasources/website.yaml", "datasources"),
            id="datasource",
        ),
        pytest.param(
            (TriggerProviderConfiguration, "triggers/events.yaml", "events"),
            id="trigger",
        ),
        pytest.param(
            (EndpointProviderConfiguration, "endpoints/provider.yaml", "endpoints"),
            id="endpoint",
        ),
    ]
)
def provider_manifest(
    request: pytest.FixtureRequest, contract_source: Path
) -> tuple[type[BaseModel], dict, str]:
    model, path, field = request.param
    return model, yaml.safe_load((contract_source / path).read_text()), field


@pytest.mark.parametrize("references", ["child.yaml", [42]])
def test_provider_rejects_invalid_declaration_references(
    provider_manifest: tuple[type[BaseModel], dict, str], references: object
) -> None:
    model, data, field = provider_manifest
    data[field] = references

    with pytest.raises((TypeError, ValidationError)):
        model.model_validate(data)


@pytest.mark.parametrize(
    ("contents", "cause"),
    [
        (None, FileNotFoundError),
        ("[", yaml.YAMLError),
        ("{}", (KeyError, ValidationError)),
    ],
    ids=["missing-file", "invalid-yaml", "missing-fields"],
)
def test_provider_reports_failed_declaration_and_keeps_original_cause(
    provider_manifest: tuple[type[BaseModel], dict, str],
    contract_source: Path,
    contents: str | None,
    cause: type[Exception] | tuple[type[Exception], ...],
) -> None:
    model, data, field = provider_manifest
    path = contract_source / "broken.yaml"
    if contents is not None:
        path.write_text(contents)
    data[field] = ["broken.yaml"]

    with pytest.raises(
        ValidationError, match=r"Error loading .* configuration"
    ) as caught:
        model.model_validate(data)

    error = caught.value.errors()[0]
    assert error["loc"] == (field,)
    assert isinstance(error["ctx"]["error"].__cause__, cause)
    if contents is None:
        assert "broken.yaml" in str(caught.value)


def test_provider_loads_declarations_in_manifest_order(
    provider_manifest: tuple[type[BaseModel], dict, str], contract_source: Path
) -> None:
    model, data, field = provider_manifest
    first = data[field][0]
    declaration = (
        deepcopy(first)
        if isinstance(first, dict)
        else yaml.safe_load((contract_source / first).read_text())
    )
    if field == "endpoints":
        declaration["path"] = "/second"
        declaration["hidden"] = True
    else:
        declaration["identity"]["name"] = "second"
        declaration["parameters"] = None
    (contract_source / "second.yaml").write_text(yaml.safe_dump(declaration))
    data[field] = ["second.yaml", first]

    loaded = getattr(model.model_validate(data), field)

    if field == "endpoints":
        assert [endpoint.path for endpoint in loaded] == ["/second", "/echo/<item>"]
        assert loaded[0].hidden
    else:
        assert [item.identity.name for item in loaded] == ["second", "echo"]
        assert loaded[0].parameters == []
    assert loaded[0].extra.python.source == declaration["extra"]["python"]["source"]


@pytest.mark.parametrize("repair_first", [False, True])
def test_tool_credentials_survive_revalidation_after_load_or_repair(
    contract_source: Path, repair_first: bool
) -> None:
    data = yaml.safe_load((contract_source / "provider/contract.yaml").read_text())
    original = deepcopy(data)
    if repair_first:
        data["tools"] = ["missing.yaml"]
        with pytest.raises(ValidationError, match=r"missing\.yaml"):
            ToolProviderConfiguration.model_validate(data)
        data["tools"] = original["tools"]
    else:
        ToolProviderConfiguration.model_validate(data)

    reloaded = ToolProviderConfiguration.model_validate(data)

    assert [credential.name for credential in reloaded.credentials_schema] == [
        "api_key"
    ]
    assert reloaded.tools[0].identity.name == "echo"


@pytest.mark.parametrize("default", [False, True])
def test_agent_manifest_preserves_boolean_parameter_defaults(
    contract_source: Path, default: bool
) -> None:
    path = contract_source / "agents/echo.yaml"
    strategy = yaml.safe_load(path.read_text())
    strategy["parameters"] = [
        {
            "name": "enable_search",
            "type": "boolean",
            "default": default,
            "label": {"en_US": "Enable search"},
        }
    ]
    path.write_text(yaml.safe_dump(strategy))
    provider = yaml.safe_load((contract_source / "agents/provider.yaml").read_text())

    configuration = AgentStrategyProviderConfiguration.model_validate(provider)

    serialized = configuration.model_dump(mode="json")
    assert serialized["strategies"][0]["parameters"][0]["default"] is default


def test_endpoint_manifest_can_mix_paths_mappings_and_parsed_declarations(
    contract_source: Path,
) -> None:
    data = yaml.safe_load((contract_source / "endpoints/provider.yaml").read_text())
    parsed = EndpointProviderConfiguration.model_validate(data).endpoints[0]
    (contract_source / "endpoint.yaml").write_text(yaml.safe_dump(data["endpoints"][0]))
    data["endpoints"] = ["endpoint.yaml", data["endpoints"][0], parsed]

    result = EndpointProviderConfiguration.model_validate(data)

    assert result.endpoints == [parsed, parsed, parsed]
    assert (
        EndpointProviderConfiguration.model_validate_json(result.model_dump_json())
        == result
    )
