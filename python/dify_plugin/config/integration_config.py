"""
This file is used to hold the integration config for plugin testing.
"""

import shutil
import subprocess

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


class IntegrationConfig(BaseSettings):
    dify_cli_path: str = Field(default="", description="The path to the dify cli")

    @field_validator("dify_cli_path")
    @classmethod
    def validate_dify_cli_path(cls, v):
        # find the dify cli path
        if not v:
            for plugin_name in _PLUGIN_NAMES:
                v = shutil.which(plugin_name)
                if v:
                    break

            if not v:
                raise ValueError("dify cli not found")

        # check dify version
        version = subprocess.check_output([v, "version"]).decode("utf-8")  # noqa: S603

        try:
            version = Version(version)
        except Exception as e:
            raise ValueError("dify cli version is not valid") from e

        if version < Version("0.1.0"):
            raise ValueError("dify cli version must be greater than 0.1.0 to support plugin run")

        return v

    model_config = SettingsConfigDict(env_file=".env")
