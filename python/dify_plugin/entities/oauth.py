from collections.abc import Sequence

from pydantic import BaseModel, Field

from dify_plugin.entities.provider_config import ProviderConfig


class OAuthSchema(BaseModel):
    client_schema: Sequence[ProviderConfig] = Field(default_factory=list, description="The schema of the OAuth client")
    credentials_schema: Sequence[ProviderConfig] = Field(
        default_factory=list, description="The schema of the OAuth credentials"
    )
