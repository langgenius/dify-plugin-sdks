from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dify_plugin.core.runtime import Session
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    Subscription,
)


@dataclass(frozen=True, slots=True)
class TriggerRuntime:
    """
    Trigger Runtime

    - session: Session
    - credentials: credentials from the trigger subscription constructor
                 Only available when the subscription is created by the
                 trigger subscription constructor
    - credential_type: Credential type
    """

    session: Session
    credential_type: CredentialType
    credentials: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EventRuntime:
    """
    Event Runtime
    """

    session: Session

    # Only available when the on_event invoke
    credential_type: CredentialType
    subscription: Subscription
    credentials: Mapping[str, Any] | None = None
