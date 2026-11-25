"""Visite Musées integration with sidebar and saved exhibition selections."""
import logging
import json
from pathlib import Path
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import (DOMAIN, NAME, PLATFORMS, PANEL_PATH, PANEL_MODULE_URL,
                    PANEL_WEB_COMPONENT, PANEL_JS_NAME, I18N_MODULE_URL,
                    FRONTEND_TRANSLATIONS_URL)
from .coordinator import VisiteMuseesCoordinator
from .selections import SelectionStore
from .websocket import async_register_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async_register_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Visite Musées %s: initializing config entry %s", NAME, entry.entry_id)
    if entry.title != NAME:
        hass.config_entries.async_update_entry(entry, title=NAME)
    coordinator = VisiteMuseesCoordinator(hass, entry)
    coordinator.selections = SelectionStore(hass, entry.entry_id)
    await coordinator.selections.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    version = await hass.async_add_executor_job(
        lambda: json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    )
    if not hass.data[DOMAIN].get("_panel_registered"):
        js_path = str(Path(__file__).parent / "frontend" / PANEL_JS_NAME)
        await hass.http.async_register_static_paths([
            StaticPathConfig(PANEL_MODULE_URL, js_path, cache_headers=False),
            StaticPathConfig(I18N_MODULE_URL, str(Path(__file__).parent / "frontend" / "i18n.js"), cache_headers=False),
            StaticPathConfig(FRONTEND_TRANSLATIONS_URL, str(Path(__file__).parent / "frontend" / "translations"), cache_headers=False)
        ])
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name=PANEL_WEB_COMPONENT,
            module_url=f"{PANEL_MODULE_URL}?v={version}",
            sidebar_title=NAME,
            sidebar_icon="mdi:palette",
            embed_iframe=False,
            require_admin=False,
        )
        hass.data[DOMAIN]["_panel_registered"] = True
        _LOGGER.info("Visite Musées %s: sidebar panel registered at /%s", version, PANEL_PATH)
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Panel/WS registration remains valid through reloads; opening panel
        # without an active config entry returns 'not_loaded'.
    return ok


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload catalog after editing departments in integration options."""
    await hass.config_entries.async_reload(entry.entry_id)
