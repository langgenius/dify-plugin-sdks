from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GridMigrationStartedEvent(CatalogSlackEvent):
    """Slack event handler for `grid.migration.started`."""

    EVENT_KEY = "grid_migration_started"
