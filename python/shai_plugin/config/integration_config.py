"""
This file is used to hold the integration config for plugin testing.
"""

import shutil
import subprocess

from packaging.version import Version
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLUGIN_NAMES = [
    "shai",
    "shai.exe", 
    "shai-plugin",
    "shai-plugin.exe",
    "shai-plugin-darwin-amd64",
    "shai-plugin-darwin-arm64",
    "shai-plugin-linux-amd64",
    "shai-plugin-linux-arm64",
    "shai-plugin-windows-amd64.exe",
    "shai-plugin-windows-arm64.exe",
]


class IntegrationConfig(BaseSettings):
    shai_cli_path: str = Field(default="", description="The path to the shai cli")

    @field_validator("shai_cli_path")
    @classmethod
    def validate_shai_cli_path(cls, v):
        # find the shai cli path
        if not v:
            for plugin_name in _PLUGIN_NAMES:
                v = shutil.which(plugin_name)
                if v:
                    break

            if not v:
                raise ValueError("shai cli not found")

        # check shai version
        version = subprocess.check_output([v, "version"]).decode("utf-8")  # noqa: S603

        try:
            version = Version(version)
        except Exception as e:
            raise ValueError("shai cli version is not valid") from e

        if version < Version("0.1.0"):
            raise ValueError("shai cli version must be greater than 0.1.0 to support plugin run")

        return v

    model_config = SettingsConfigDict(env_file=".env", extra="allow")
