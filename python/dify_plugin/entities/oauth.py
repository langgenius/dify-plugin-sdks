from collections.abc import Mapping, Sequence
from typing import Any

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


class OAuthCredentials(BaseModel):
    credentials: Mapping[str, Any] = Field(..., description="The credentials of the OAuth")
    expires_at: int = Field(
        default=-1, description="The timestamp of the credentials expiration, -1 means never expires"
    )
