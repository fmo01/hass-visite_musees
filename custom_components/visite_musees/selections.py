"""Persistent personal exhibition lists and durable visit history."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date

from homeassistant.helpers.storage import Store
from .const import STORAGE_SELECTION_KEY_PREFIX


def event_id(event: dict) -> str:
    """Stable across source changes and date edits (museum + normalized title)."""
    title = unicodedata.normalize("NFKD", event.get("title", ""))
    title = "".join(c for c in title if not unicodedata.combining(c)).casefold()
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()
    raw = f"{event.get('museum_id', '')}|{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


SNAPSHOT_KEYS = ("museum_id", "title", "start", "end", "url", "image", "source")


class SelectionStore:
    """Keep snapshots when an exhibition disappears from the public catalog."""

    def __init__(self, hass, entry_id: str):
        # Retain the existing storage version/key so existing saved/hidden lists load.
        self.store = Store(hass, 1, f"{STORAGE_SELECTION_KEY_PREFIX}.{entry_id}")
        self._data: dict = {"saved": {}, "hidden": {}, "visits": {}}

    async def async_load(self):
        loaded = await self.store.async_load()
        if isinstance(loaded, dict):
            for field in ("saved", "hidden", "visits"):
                if isinstance(loaded.get(field), dict):
                    self._data[field] = loaded[field]

    def serialized(self) -> dict:
        return {key: dict(value) for key, value in self._data.items()}

    async def async_set(self, group: str, event: dict, enabled: bool):
        if group not in ("saved", "hidden"):
            raise ValueError("invalid group")
        identifier = event_id(event)
        if enabled:
            self._data[group][identifier] = {key: event.get(key) for key in SNAPSHOT_KEYS}
        else:
            self._data[group].pop(identifier, None)
        await self.store.async_save(self._data)
        return identifier

    async def async_set_visit(self, event: dict, visit_date: str | None, visited: bool):
        """Create/update a planned or completed visit; preserve snapshots indefinitely.

        Clearing the date without confirming a visit removes the plan. A completed
        visit may keep its date (historical) and remains after feed expiry.
        """
        if visit_date is not None:
            if not isinstance(visit_date, str):
                raise ValueError("invalid visit date")
            try:
                parsed = date.fromisoformat(visit_date)
            except ValueError as err:
                raise ValueError("invalid visit date") from err
            if parsed.isoformat() != visit_date:
                raise ValueError("invalid visit date")
        if not isinstance(visited, bool):
            raise ValueError("invalid visit status")
        identifier = event_id(event)
        if visit_date is None and not visited:
            self._data["visits"].pop(identifier, None)
        else:
            self._data["visits"][identifier] = {
                **{key: event.get(key) for key in SNAPSHOT_KEYS},
                "visit_date": visit_date,
                "visited": visited,
            }
        await self.store.async_save(self._data)
        return identifier
