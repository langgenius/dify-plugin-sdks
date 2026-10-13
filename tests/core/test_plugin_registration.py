from pathlib import Path

import pytest
import yaml

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.plugin_registration import PluginRegistration

from .plugin_fixtures import contract_source

__all__ = ["contract_source"]


def remove_constructor_export(source: Path) -> None:
    dispatch = source / "triggers/dispatch.py"
    dispatch.write_text(
        dispatch.read_text().replace(
            "from triggers.constructor import ContractConstructor\n", ""
        )
    )


def test_subscription_constructor_loads_its_declared_source(
    contract_source: Path,
) -> None:
    remove_constructor_export(contract_source)
    provider_file = contract_source / "triggers/events.yaml"
    provider = yaml.safe_load(provider_file.read_text())
    provider["subscription_constructor"]["extra"] = {
        "python": {"source": "triggers/constructor.py"}
    }
    provider_file.write_text(yaml.safe_dump(provider))

    registration = PluginRegistration(DifyPluginEnv())

    constructor = registration.trigger_factory.get_subscription_constructor_cls(
        "events"
    )
    assert constructor is not None
    assert constructor.__name__ == "ContractConstructor"
    assert constructor.__module__ == "triggers.constructor"


def test_subscription_constructor_requires_one_implementation(
    contract_source: Path,
) -> None:
    remove_constructor_export(contract_source)

    with pytest.raises(
        ValueError, match="configuration declared but no implementation"
    ):
        PluginRegistration(DifyPluginEnv())


def test_subscription_constructor_rejects_multiple_implementations(
    contract_source: Path,
) -> None:
    dispatch = contract_source / "triggers/dispatch.py"
    dispatch.write_text(
        dispatch.read_text()
        + "\nclass DuplicateConstructor(ContractConstructor):\n    pass\n"
    )

    with pytest.raises(ValueError, match="Multiple TriggerSubscriptionConstructor"):
        PluginRegistration(DifyPluginEnv())


def test_trigger_without_subscription_configuration_is_supported(
    contract_source: Path,
) -> None:
    remove_constructor_export(contract_source)
    provider_file = contract_source / "triggers/events.yaml"
    provider = yaml.safe_load(provider_file.read_text())
    provider.pop("subscription_constructor")
    provider_file.write_text(yaml.safe_dump(provider))

    registration = PluginRegistration(DifyPluginEnv())

    assert (
        registration.trigger_factory.get_subscription_constructor_cls("events") is None
    )
    assert (
        registration.trigger_factory.get_configuration("events").events[0].identity.name
        == "echo"
    )


@pytest.mark.parametrize("missing_file", ["manifest.yaml", "provider/contract.yaml"])
def test_missing_configuration_has_context_and_cause(
    contract_source: Path, missing_file: str
) -> None:
    (contract_source / missing_file).unlink()

    with pytest.raises(ValueError, match="Error loading plugin configuration") as error:
        PluginRegistration(DifyPluginEnv())

    assert error.value.__cause__ is not None
    assert missing_file in str(error.value)


def test_invalid_manifest_does_not_start_loading_implementations(
    contract_source: Path,
) -> None:
    manifest = contract_source / "manifest.yaml"
    manifest.write_text("version: invalid\n")

    with pytest.raises(ValueError, match="Error loading plugin configuration") as error:
        PluginRegistration(DifyPluginEnv())

    assert "validation error" in str(error.value)


def test_assets_load_binary_files_without_directories(contract_source: Path) -> None:
    assets = contract_source / "_assets"
    (assets / "empty.bin").touch()
    (assets / "binary.bin").write_bytes(bytes(range(256)))
    nested = assets / "nested"
    nested.mkdir()
    (nested / "ignored.txt").write_text("ignored")

    registration = PluginRegistration(DifyPluginEnv())

    files = {asset.filename: asset.data for asset in registration.files}
    assert files["empty.bin"] == b""
    assert files["binary.bin"] == bytes(range(256))
    assert "nested" not in files
    assert "ignored.txt" not in files
