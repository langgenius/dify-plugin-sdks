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
    hidden: bool = Field(
        default=False, description="Whether to hide this endpoint in the UI"
    )
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
    def validate_endpoints(cls, value: list[object]) -> list[EndpointConfiguration]:
        if not isinstance(value, list):
            msg = "endpoints should be a list"
            raise ValueError(msg)

        endpoints: list[EndpointConfiguration] = []

        for raw_endpoint in value:
            # read from yaml or load directly
            if isinstance(raw_endpoint, EndpointConfiguration | dict):
                endpoint_config = (
                    EndpointConfiguration(**raw_endpoint)
                    if isinstance(raw_endpoint, dict)
                    else raw_endpoint
                )
                endpoints.append(endpoint_config)
                continue

            if not isinstance(raw_endpoint, str):
                msg = "endpoint path should be a string"
                raise ValueError(msg)

            try:
                file = cls._load_yaml_file(raw_endpoint)
                endpoints.append(EndpointConfiguration(**file))
            except Exception as e:
                msg = f"Error loading endpoint configuration: {e!s}"
                raise ValueError(msg) from e

        return endpoints
