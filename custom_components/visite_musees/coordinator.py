"""Multi-source polling with persistent cache and per-source status."""
from __future__ import annotations
import asyncio
import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    DOMAIN, PARIS_EVENTS_API_URL, MUSEOFILE_DATASET_API_URL,
    OFFICIAL_EXHIBITION_URLS, OFFICIAL_MUSEUM_ALIASES, STORAGE_CACHE_KEY_PREFIX,
)
from .geo_departments import async_get_departments
from .official import official_exhibitions
from .museum_registry import (DEFAULT_DEPARTMENTS, select_resource,
                              tabular_url, parse_json_catalogue, filter_departments, normalized, set_geo_departments)

_LOGGER = logging.getLogger(__name__)

def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c)).lower()).strip()

def classify(event, today):
    try:
        start = date.fromisoformat(event["start"][:10])
        end = date.fromisoformat(event["end"][:10])
    except (KeyError, ValueError, TypeError): return "dates_inconnues"
    return "terminee" if end < today else "a_venir" if start > today else "en_cours"

def match_museum(item, museums):
    location = normalize(item.get("address_name", ""))
    for museum in museums:
        if location == normalize(museum["name"]) or any(location == normalize(a) for a in museum.get("aliases", [])):
            return museum["id"]
    return None

def normalize_paris(item, museums):
    mid = match_museum(item, museums)
    tags = normalize(item.get("qfap_tags", "") or item.get("universe_tags", ""))
    if mid is None or "expo" not in tags: return None
    if not item.get("date_start") or not item.get("date_end") or not item.get("title"): return None
    return {"museum_id": mid, "title": item["title"], "start": str(item["date_start"])[:10],
            "end": str(item["date_end"])[:10], "url": item.get("url", ""),
            "image": item.get("cover_url"), "price_type": item.get("price_type"),
            "source": "opendata_paris", "verified_at": date.today().isoformat()}

class VisiteMuseesCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=6))
        self.museums = []
        self.departments = list(entry.options.get("departments", entry.data.get("departments", DEFAULT_DEPARTMENTS)))
        self.store = Store(hass, 1, f"{STORAGE_CACHE_KEY_PREFIX}.{entry.entry_id}")
        self._cache = None

    async def _async_fetch_tabular_resource(self, session, resource_id):
        """Download every page before accepting a new national catalogue.

        Pagination stays on our fixed trusted API host, rather than following
        arbitrary URLs supplied in the response.
        """
        url = tabular_url(resource_id)
        rows = []
        page = 1
        page_size = 100
        expected_total = None
        while True:
            if page > 2000:
                raise ValueError("Muséofile JSON: trop de pages")
            async with asyncio.timeout(35):
                async with session.get(url, params={"page": page, "page_size": page_size}) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError(f"Muséofile JSON: réponse invalide, page {page}")
            batch = payload["data"]
            meta = payload.get("meta") or {}
            if expected_total is None:
                value = meta.get("total")
                expected_total = int(value) if value is not None else None
                if expected_total is not None and expected_total <= 0:
                    raise ValueError("Muséofile JSON: référentiel vide")
            if not batch and (expected_total is None or len(rows) < expected_total):
                raise ValueError(f"Muséofile JSON: page {page} vide avant la fin")
            rows.extend(batch)
            if expected_total is not None and len(rows) >= expected_total:
                if len(rows) != expected_total:
                    raise ValueError("Muséofile JSON: pagination incohérente")
                break
            next_url = (payload.get("links") or {}).get("next")
            if not next_url:
                if expected_total is not None and len(rows) != expected_total:
                    raise ValueError("Muséofile JSON: données incomplètes")
                break
            page += 1
        return parse_json_catalogue(rows)

    async def _async_update_data(self):
        if self._cache is None:
            self._cache = await self.store.async_load() or {"by_source": {}, "sources": {}}
        cache = self._cache
        by_source = dict(cache.get("by_source", {}))
        sources = dict(cache.get("sources", {}))
        session = async_get_clientsession(self.hass)
        stamp = datetime.now(timezone.utc).isoformat()
        geo_ready = False
        try:
            geo_departments = await async_get_departments(self.hass)
            set_geo_departments(geo_departments)
            geo_ready = True
        except Exception as exc:
            _LOGGER.warning("Official geographic departments unavailable: %s", exc)
        # Muséofile national is the sole museum registry; keep the last valid
        # complete catalogue during transient outages, never use museums.json.
        last_registry = cache.get("national_registry_checked_at")
        needs_registry = (not cache.get("national_registry") or
                          cache.get("national_registry_method") != "tabular_api_json")
        if last_registry:
            try:
                needs_registry = (datetime.fromisoformat(last_registry) <
                                  datetime.now(timezone.utc) - timedelta(days=7))
            except ValueError:
                needs_registry = True
        if needs_registry and geo_ready:
            try:
                async with asyncio.timeout(30):
                    async with session.get(MUSEOFILE_DATASET_API_URL) as response:
                        response.raise_for_status()
                        dataset = await response.json()
                resource_ids = select_resource(dataset)
                records = None
                resource_errors = []
                for resource_id in resource_ids:
                    try:
                        records = await self._async_fetch_tabular_resource(session, resource_id)
                        break
                    except Exception as resource_exc:
                        resource_errors.append(f"{resource_id}: {resource_exc}")
                if records is None:
                    raise ValueError("API tabulaire Muséofile indisponible : " + "; ".join(resource_errors)[:400])
                cache["national_registry"] = records
                cache["national_registry_method"] = "tabular_api_json"
                cache["national_registry_checked_at"] = stamp
                sources["museofile_national"] = {
                    "status": "ok", "count": len(records), "checked_at": stamp,
                    "resource_id": resource_id, "method": "tabular_api_json"
                }
            except Exception as exc:
                _LOGGER.warning("National Muséofile registry unavailable: %s", exc)
                sources["museofile_national"] = {
                    "status": "error", "message": str(exc)[:160],
                    "checked_at": stamp,
                    "cached_count": len(cache.get("national_registry", [])),
                }
        self.museums = filter_departments(cache.get("national_registry", []), self.departments)
        if not self.museums and not cache.get("national_registry"):
            _LOGGER.warning("No national Muséofile museum catalogue available yet")
        # Keep official exhibition sources independent of the museum web address
        # published by Muséofile, which is often a general museum homepage.
        official_urls = OFFICIAL_EXHIBITION_URLS
        official_names = OFFICIAL_MUSEUM_ALIASES
        for mid in ("mad", "orsay"):
            museum = next((m for m in self.museums if any(
                alias in normalized(m["name"]) or any(alias in normalized(a) for a in m.get("aliases", []))
                for alias in official_names[mid]
            )), None)
            if museum is None:
                continue
            source = f"official_{mid}"
            try:
                async with asyncio.timeout(30):
                    async with session.get(official_urls[mid]) as response:
                        response.raise_for_status()
                        html = await response.text()
                events = official_exhibitions(html, mid, official_urls[mid])
                if not events:
                    raise ValueError("No dated exhibitions extracted; HTML structure must be reviewed")
                for event in events:
                    event["museum_id"] = museum["id"]
                by_source[source] = events
                sources[source] = {"status":"ok", "count":len(events), "checked_at":stamp}
            except Exception as exc:
                if mid == "orsay" and getattr(exc, "status", None) == 403:
                    message = "HTTP 403 : accès automatisé refusé par le site officiel d'Orsay"
                else:
                    message = str(exc)
                _LOGGER.warning("Source %s unavailable: %s", source, message)
                sources[source] = {"status":"blocked" if mid == "orsay" and getattr(exc, "status", None) == 403 else "error", "message":message[:160],
                                   "checked_at":stamp, "cached_count":len(by_source.get(source, []))}
        try:
            events = []; offset = 0; total = 0
            while True:
                async with asyncio.timeout(30):
                    async with session.get(PARIS_EVENTS_API_URL, params={"limit":100,"offset":offset}) as response:
                        response.raise_for_status()
                        payload = await response.json()
                batch=payload.get("results",[]); total=payload.get("total_count", 0)
                for obj in batch:
                    e=normalize_paris(obj, self.museums)
                    if e: events.append(e)
                offset += len(batch)
                if not batch or offset>=total: break
                if offset>=10000: raise ValueError("OpenData pagination exceeded 10000 entries")
            by_source["opendata_paris"] = events
            sources["opendata_paris"] = {"status":"ok","count":len(events),"checked_at":stamp}
        except Exception as exc:
            _LOGGER.warning("OpenData unavailable: %s", exc)
            sources["opendata_paris"] = {"status":"error","message":str(exc)[:160],
                                          "checked_at":stamp,"cached_count":len(by_source.get("opendata_paris",[]))}
        # Discard obsolete regional and curated caches; keep personal selections
        # in their independent store untouched.
        by_source.pop("museofile_idf", None)
        sources.pop("museofile_idf", None)
        cache.pop("museum_registry", None)
        cache.pop("museum_registry_checked_at", None)
        self._cache = {**cache, "by_source":by_source,"sources":sources}
        await self.store.async_save(self._cache)
        unique = {}
        # Official sources win over OpenData for the same exhibition.
        valid_museums = {museum["id"] for museum in self.museums}
        for source in ["opendata_paris", "official_mad", "official_orsay"]:
            for e in by_source.get(source, []):
                if e["museum_id"] not in valid_museums:
                    continue
                key = (e["museum_id"], normalize(e["title"]), e["start"])
                unique[key] = e
        today = datetime.now(timezone.utc).astimezone().date()
        active = []
        for e in unique.values():
            e=dict(e); e["status"]=classify(e,today)
            if e["status"] in ("en_cours","a_venir"): active.append(e)
        active.sort(key=lambda e:(e["start"], e["museum_id"], e["title"]))
        return {"museums":self.museums,"events":active,"sources":sources,"updated_at":stamp}
