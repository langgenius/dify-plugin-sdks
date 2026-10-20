from typing import Literal

from pydantic import BaseModel, StrictBool

AuthReasonCode = Literal[
    "credential_invalid",
    "credential_expired",
    "credential_revoked",
    "provider_timeout",
    "provider_network_error",
    "provider_rate_limited",
    "provider_unavailable",
]


class CredentialCheckResult(BaseModel):
    """Provider-classified outcome; retryable indicates whether to try again later.

    A null reason_code means the provider supplied no more specific reason.
    """

    status: Literal["valid", "invalid", "temporarily_unavailable", "unsupported"]
    reason_code: AuthReasonCode | None
    retryable: StrictBool
