from .const import DOMAIN, NAME
"""Calendar of exhibition periods (not museum visiting slots)."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity

TZ = ZoneInfo("Europe/Paris")

async def async_setup_entry(hass, entry, async_add_entities):
    from .const import DOMAIN
    async_add_entities([VisiteMuseesCalendar(hass.data[DOMAIN][entry.entry_id])])

class VisiteMuseesCalendar(CoordinatorEntity, CalendarEntity):
    _attr_name = "Expositions"
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_expositions_calendar"
    _attr_icon = "mdi:calendar-star"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "catalogue")}, "name": NAME}

    def _events(self):
        data = self.coordinator.data or {"events": [], "museums": []}
        names = {m["id"]: m["name"] for m in data["museums"]}
        result = []
        for e in data["events"]:
            try:
                start = datetime.combine(datetime.fromisoformat(e["start"][:10]).date(), time.min, TZ)
                end = datetime.combine(datetime.fromisoformat(e["end"][:10]).date() + timedelta(days=1), time.min, TZ)
            except (ValueError, TypeError, KeyError):
                continue
            result.append(CalendarEvent(start=start, end=end,
                summary=f"{names.get(e['museum_id'], e['museum_id'])} — {e['title']}",
                description=f"Source : {e['source']} | Dernière collecte : {e.get('verified_at', '?')}\n{e.get('url', '')}"))
        return sorted(result, key=lambda e: e.start)

    @property
    def event(self):
        now = datetime.now(TZ)
        return next((e for e in self._events() if e.start <= now < e.end), None)

    async def async_get_events(self, hass, start_date, end_date):
        return [e for e in self._events() if e.start < end_date and e.end > start_date]
