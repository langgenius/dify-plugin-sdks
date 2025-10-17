from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GridMigrationFinishedEvent(CatalogSlackEvent):
    """Slack event handler for `grid.migration.finished`."""

    EVENT_KEY = "grid_migration_finished"
