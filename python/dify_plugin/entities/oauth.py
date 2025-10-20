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
    metadata: Mapping[str, Any] = Field(default_factory=dict, description="The metadata like avatar_url, name, etc.")
    credentials: Mapping[str, Any] = Field(..., description="The credentials of the OAuth")
    expires_at: int = Field(
        default=-1, description="The timestamp of the credentials expiration, -1 means never expires"
    )


class ToolOAuthCredentials(BaseModel):
    credentials: Mapping[str, Any] = Field(..., description="The credentials of the tool")
    expires_at: int | None = Field(
        default=-1,
        description="""The expiration timestamp (in seconds since Unix epoch, UTC) of the credentials.
        Set to -1 or None if the credentials do not expire.""",
    )


class TriggerOAuthCredentials(BaseModel):
    credentials: Mapping[str, Any] = Field(..., description="The credentials of the trigger")
    expires_at: int | None = Field(
        default=-1,
        description="""The expiration timestamp (in seconds since Unix epoch, UTC) of the credentials.
        Set to -1 or None if the credentials do not expire.""",
    )
