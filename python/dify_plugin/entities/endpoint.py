from pydantic import BaseModel, Field, field_validator

from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities.tool import ProviderConfig


class EndpointConfigurationExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


class EndpointConfiguration(BaseModel):
    path: str
    method: str
    hidden: bool = Field(default=False, description="Whether to hide this endpoint in the UI")
    extra: EndpointConfigurationExtra


class EndpointProviderConfiguration(BaseModel):
    settings: list[ProviderConfig] = Field(default_factory=list)
    endpoints: list[EndpointConfiguration] = Field(default_factory=list)

    @field_validator("endpoints", mode="before")
    @classmethod
    def validate_endpoints(cls, value) -> list[EndpointConfiguration]:
        if not isinstance(value, list):
            raise ValueError("endpoints should be a list")

        endpoints: list[EndpointConfiguration] = []

        for endpoint in value:
            # read from yaml
            if not isinstance(endpoint, str):
                raise ValueError("endpoint path should be a string")
            try:
                file = load_yaml_file(endpoint)
                endpoints.append(EndpointConfiguration(**file))
            except Exception as e:
                raise ValueError(f"Error loading endpoint configuration: {e!s}") from e

        return endpoints
