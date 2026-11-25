from .const import DOMAIN, NAME
"""Catalogue metrics. Individual exhibitions live in calendar, not sensor attributes."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

SENSORS = (
    ("musees", "Musées référencés", "museums"),
    ("en_cours", "Expositions en cours", "en_cours"),
    ("a_venir", "Expositions à venir", "a_venir"),
    ("gratuites", "Expositions gratuites", "gratuites"),
)

async def async_setup_entry(hass, entry, async_add_entities):
    from .const import DOMAIN
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(VisiteMuseesSensor(coordinator, *spec) for spec in SENSORS)

class VisiteMuseesSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:palette"

    def __init__(self, coordinator, key, name, metric):
        super().__init__(coordinator)
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "catalogue")}, "name": NAME}

    @property
    def native_value(self):
        data = self.coordinator.data or {"events": [], "museums": []}
        if self._metric == "museums":
            return len(data["museums"])
        if self._metric == "gratuites":
            return sum(e.get("price_type") == "gratuit" for e in data["events"])
        return sum(e["status"] == self._metric for e in data["events"])

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"last_update": data.get("updated_at"),
                "sources": data.get("sources", {}),
                "note": "Catalogue partiel; collecte officielle MAD/Orsay en phase pilote"}
