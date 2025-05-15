"""
This file is used to hold the integration config for plugin testing.
"""

import shutil
import subprocess
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from packaging.version import Version


class IntegrationConfig(BaseSettings):
    dify_cli_path: str = Field(default="", description="The path to the dify cli")

    @field_validator("dify_cli_path")
    def validate_dify_cli_path(cls, v):
        # find the dify cli path
        if not v:
            v = shutil.which("dify")
            if not v:
                raise ValueError("dify cli not found")
            # check dify version
            version = subprocess.check_output([v, "version"]).decode("utf-8")
            try:
                version = Version(version)
            except Exception:
                raise ValueError("dify cli version is not valid")

            if version < Version("0.4.0"):
                raise ValueError("dify cli version must be greater than 0.4.0 to support plugin run")

        return v

    model_config = SettingsConfigDict(env_file=".env")
