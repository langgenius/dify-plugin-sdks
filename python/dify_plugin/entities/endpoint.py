from pydantic import BaseModel, Field, field_validator

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities.tool import ProviderConfig


@docs(
    name="EndpointExtra",
    description="The extra of the endpoint",
)
class EndpointConfigurationExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


@docs(
    name="Endpoint",
    description="The Manifest of the endpoint",
)
class EndpointConfiguration(BaseModel):
    path: str
    method: str
    hidden: bool = Field(default=False, description="Whether to hide this endpoint in the UI")
    extra: EndpointConfigurationExtra


@docs(
    name="EndpointGroup",
    description="The Manifest of the endpoint group",
    outside_reference_fields={"endpoints": EndpointConfiguration},
)
class EndpointProviderConfiguration(BaseModel):
    settings: list[ProviderConfig] = Field(default_factory=list)
    endpoints: list[EndpointConfiguration] = Field(default_factory=list)

    @classmethod
    def _load_yaml_file(cls, path: str) -> dict:
        return load_yaml_file(path)

    @field_validator("endpoints", mode="before")
    @classmethod
    def validate_endpoints(cls, value) -> list[EndpointConfiguration]:
        if not isinstance(value, list):
            raise ValueError("endpoints should be a list")

        endpoints: list[EndpointConfiguration] = []

        for endpoint in value:
            # read from yaml or load directly
            if isinstance(endpoint, EndpointConfiguration | dict):
                if isinstance(endpoint, dict):
                    endpoint = EndpointConfiguration(**endpoint)
                endpoints.append(endpoint)
                continue

            if not isinstance(endpoint, str):
                raise ValueError("endpoint path should be a string")

            try:
                file = cls._load_yaml_file(endpoint)
                endpoints.append(EndpointConfiguration(**file))
            except Exception as e:
                raise ValueError(f"Error loading endpoint configuration: {e!s}") from e

        return endpoints
