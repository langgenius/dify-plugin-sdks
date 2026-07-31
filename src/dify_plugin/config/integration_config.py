"""This file is used to hold the integration config for plugin testing."""

import os
import shutil
import subprocess  # ruff:ignore[suspicious-subprocess-import]

from packaging.version import Version
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLUGIN_NAMES = [
    "dify",
    "dify.exe",
    "dify-plugin",
    "dify-plugin.exe",
    "dify-plugin-darwin-amd64",
    "dify-plugin-darwin-arm64",
    "dify-plugin-linux-amd64",
    "dify-plugin-linux-arm64",
    "dify-plugin-windows-amd64.exe",
    "dify-plugin-windows-arm64.exe",
]


def find_dify_cli_path() -> str | None:
    configured_path = os.getenv("DIFY_CLI_PATH")
    if configured_path:
        return configured_path

    for plugin_name in _PLUGIN_NAMES:
        cli_path = shutil.which(plugin_name)
        if cli_path:
            return cli_path

    return None


class IntegrationConfig(BaseSettings):
    dify_cli_path: str = Field(default="", description="The path to the dify cli")

    @field_validator("dify_cli_path")
    @classmethod
    def validate_dify_cli_path(cls, v: str) -> str:
        # find the dify cli path
        if not v:
            v = find_dify_cli_path()

            if not v:
                msg = "dify cli not found"
                raise ValueError(msg)

        # check dify version
        version = subprocess.check_output([v, "version"]).decode("utf-8")  # ruff:ignore[subprocess-without-shell-equals-true]

        try:
            version = Version(version)
        except Exception as e:
            msg = "dify cli version is not valid"
            raise ValueError(msg) from e

        if version < Version("0.1.0"):
            msg = "dify cli version must be greater than 0.1.0 to support plugin run"
            raise ValueError(
                msg,
            )

        return v

    model_config = SettingsConfigDict(env_file=".env", extra="allow")
