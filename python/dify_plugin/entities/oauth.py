from collections.abc import Sequence

from pydantic import BaseModel, Field

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.entities.provider_config import ProviderConfig


@docs(
    name="OAuthSchema",
    description="The schema of the OAuth",
)
class OAuthSchema(BaseModel):
    client_schema: Sequence[ProviderConfig] = Field(default_factory=list, description="The schema of the OAuth client")
    credentials_schema: Sequence[ProviderConfig] = Field(
        default_factory=list, description="The schema of the OAuth credentials"
    )
