from collections.abc import Mapping
from typing import Any

from dify_plugin.core.runtime import Session
from dify_plugin.entities.provider_config import CredentialType
from dify_plugin.entities.trigger import (
    Subscription,
)


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
    credentials: Mapping[str, Any] | None = None
    credential_type: CredentialType = CredentialType.UNAUTHORIZED

    def __init__(
        self,
        session: Session,
        credential_type: CredentialType,
        credentials: Mapping[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.credentials = credentials
        self.credential_type = credential_type


class EventRuntime:
    """
    Event Runtime
    """

    session: Session

    # Only available when the on_event invoke
    subscription: Subscription
    credentials: Mapping[str, Any] | None = None
    credential_type: CredentialType = CredentialType.UNAUTHORIZED

    def __init__(
        self,
        session: Session,
        credential_type: CredentialType,
        subscription: Subscription,
        credentials: Mapping[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.subscription = subscription
        self.credentials = credentials
        self.credential_type = credential_type
