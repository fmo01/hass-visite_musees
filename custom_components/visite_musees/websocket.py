"""WebSocket endpoints for catalog and persistent selections."""
from __future__ import annotations
import voluptuous as vol
from .const import WS_PREFIX
from homeassistant.components import websocket_api
from homeassistant.core import callback
from .const import DOMAIN
from .selections import event_id


def _instance(hass):
    entries = hass.data.get(DOMAIN, {})
    return next((item for item in entries.values() if hasattr(item, "selections")), None)


@websocket_api.websocket_command({vol.Required("type"): f"{WS_PREFIX}/catalog"})
@callback
def ws_catalog(hass, connection, msg):
    coordinator = _instance(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    data = coordinator.data or {"museums": coordinator.museums, "events": [], "sources": {}}
    events = [{**event, "id": event_id(event)} for event in data["events"]]
    connection.send_result(msg["id"], {
        **data, "events": events, "selections": coordinator.selections.serialized()
    })


@websocket_api.websocket_command({
    vol.Required("type"): f"{WS_PREFIX}/mark",
    vol.Required("group"): vol.In(("saved", "hidden")),
    vol.Required("event_id"): str,
    vol.Required("enabled"): bool,
})
@websocket_api.async_response
async def ws_mark(hass, connection, msg):
    coordinator = _instance(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    group = msg["group"]
    eid = msg["event_id"]
    data = coordinator.data or {}
    event = next((x for x in data.get("events", []) if event_id(x) == eid), None)
    if event is None:
        selection_data = coordinator.selections.serialized()
        event = next((selection_data[k][eid] for k in ("saved", "hidden", "visits") if eid in selection_data[k]), None)
    if event is None:
        connection.send_error(msg["id"], "not_found", "Exhibition not found")
        return
    await coordinator.selections.async_set(group, event, msg["enabled"])
    connection.send_result(msg["id"], {"selections": coordinator.selections.serialized()})


@websocket_api.websocket_command({
    vol.Required("type"): f"{WS_PREFIX}/visit",
    vol.Required("event_id"): str,
    vol.Required("visit_date"): vol.Any(None, str),
    vol.Required("visited"): bool,
})
@websocket_api.async_response
async def ws_visit(hass, connection, msg):
    coordinator = _instance(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    eid = msg["event_id"]
    event = next((e for e in (coordinator.data or {}).get("events", []) if event_id(e) == eid), None)
    if event is None:
        selections = coordinator.selections.serialized()
        event = next((selections[k][eid] for k in ("visits", "saved", "hidden") if eid in selections[k]), None)
    if event is None:
        connection.send_error(msg["id"], "not_found", "Exhibition not found")
        return
    try:
        await coordinator.selections.async_set_visit(event, msg["visit_date"], msg["visited"])
    except ValueError as exc:
        connection.send_error(msg["id"], "invalid_date", str(exc))
        return
    connection.send_result(msg["id"], {"selections": coordinator.selections.serialized()})


@websocket_api.websocket_command({vol.Required("type"): f"{WS_PREFIX}/refresh"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh(hass, connection, msg):
    coordinator = _instance(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"updated_at": (coordinator.data or {}).get("updated_at")})


def async_register_commands(hass):
    websocket_api.async_register_command(hass, ws_catalog)
    websocket_api.async_register_command(hass, ws_mark)
    websocket_api.async_register_command(hass, ws_visit)
    websocket_api.async_register_command(hass, ws_refresh)
