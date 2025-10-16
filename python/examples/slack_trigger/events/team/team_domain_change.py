from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class TeamDomainChangeEvent(CatalogSlackEvent):
    """Slack event handler for `team.domain.change`."""

    EVENT_KEY = "team_domain_change"
