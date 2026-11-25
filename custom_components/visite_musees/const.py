"""Canonical integration configuration and network endpoint constants."""

DOMAIN = "visite_musees"
NAME = "Visite Musées"
PLATFORMS = ["sensor", "calendar"]

# Network endpoints: single source of truth for the entire Python integration.
MUSEOFILE_DATASET_API_URL = (
    "https://www.data.gouv.fr/api/1/datasets/musees-de-france-base-museofile/"
)
TABULAR_API_BASE_URL = "https://tabular-api.data.gouv.fr/api/resources"
GEO_DEPARTMENTS_API_URL = (
    "https://geo.api.gouv.fr/departements?fields=nom,code,codeRegion"
)
PARIS_EVENTS_API_URL = (
    "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
    "que-faire-a-paris-/records"
)
OFFICIAL_EXHIBITION_URLS = {
    "mad": "https://madparis.fr/Expositions-en-cours-501",
    "orsay": "https://www.musee-orsay.fr/fr/programme/agenda/expositions",
}
OFFICIAL_MUSEUM_ALIASES = {
    "mad": ("musee des arts decoratifs", "musee des arts decoratifs de paris"),
    "orsay": ("musee d orsay",),
}

# Panel, frontend, websocket and storage identifiers.
PANEL_PATH = "visite-musees"
FRONTEND_BASE_URL = "/visite_musees_static"
PANEL_JS_NAME = "visite-musees-panel.js"
PANEL_WEB_COMPONENT = "visite-musees-panel"
PANEL_MODULE_URL = f"{FRONTEND_BASE_URL}/{PANEL_JS_NAME}"
I18N_MODULE_URL = f"{FRONTEND_BASE_URL}/i18n.js"
FRONTEND_TRANSLATIONS_URL = f"{FRONTEND_BASE_URL}/translations"
STORAGE_GEO_KEY = f"{DOMAIN}.geo_departments"
STORAGE_CACHE_KEY_PREFIX = DOMAIN
STORAGE_SELECTION_KEY_PREFIX = f"{DOMAIN}.selections"
WS_PREFIX = DOMAIN
