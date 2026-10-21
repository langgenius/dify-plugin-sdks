import pytest
from pydantic import ValidationError

from dify_plugin.core.entities.plugin.setup import (
    PluginArch,
    PluginConfiguration,
    PluginLanguage,
)


@pytest.mark.parametrize("minimum_version", [None, "1.0.0", "1.0.0rc1"])
def test_optional_minimum_dify_required(minimum_version: str | None) -> None:
    meta = PluginConfiguration.Meta(
        version="1.0.0",
        arch=[PluginArch.AMD64, PluginArch.ARM64],
        runner=PluginConfiguration.Meta.PluginRunner(
            language=PluginLanguage.PYTHON, version="3.10", entrypoint="main.py"
        ),
        minimum_dify_version=minimum_version,
    )

    assert meta.minimum_dify_version == minimum_version

    meta = PluginConfiguration.Meta(
        version="1.0.0",
        arch=[PluginArch.AMD64, PluginArch.ARM64],
        runner=PluginConfiguration.Meta.PluginRunner(
            language=PluginLanguage.PYTHON, version="3.10", entrypoint="main.py"
        ),
    )

    assert meta.minimum_dify_version is None


@pytest.mark.parametrize("minimum_version", ["", "not-a-version"])
def test_invalid_minimum_dify_version_is_rejected(minimum_version: str) -> None:
    with pytest.raises(ValidationError, match="Invalid version format"):
        PluginConfiguration.Meta(
            version="1.0.0",
            arch=[PluginArch.AMD64],
            runner=PluginConfiguration.Meta.PluginRunner(
                language=PluginLanguage.PYTHON, version="3.12", entrypoint="main.py"
            ),
            minimum_dify_version=minimum_version,
        )
