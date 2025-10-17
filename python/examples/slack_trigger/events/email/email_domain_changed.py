from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class EmailDomainChangedEvent(CatalogSlackEvent):
    """Slack event handler for `email.domain.changed`."""

    EVENT_KEY = "email_domain_changed"
