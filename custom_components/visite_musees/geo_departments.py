"""Official French departments from the national geographic API."""
from __future__ import annotations

import re
import unicodedata

from .const import DOMAIN, GEO_DEPARTMENTS_API_URL, STORAGE_GEO_KEY


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def validate_departments(payload):
    """Validate a complete-looking list before caching or using it."""
    if not isinstance(payload, list):
        raise ValueError("API Géo : liste de départements invalide")
    result = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        name = item.get("nom")
        if not isinstance(code, str) or not isinstance(name, str):
            continue
        if not re.fullmatch(r"(?:\d{2}|2[AB]|97[1-6])", code) or not name.strip():
            continue
        result[code] = {"code": code, "nom": name.strip(), "codeRegion": item.get("codeRegion", "")}
    if len(result) < 90 or "75" not in result or "2A" not in result or "971" not in result:
        raise ValueError("API Géo : catalogue de départements incomplet")
    return sorted(result.values(), key=lambda x: (x["nom"].casefold(), x["code"]))


def lookup_codes(departments):
    by_code = {item["code"].upper(): item["code"] for item in departments}
    by_name = {normalize(item["nom"]): item["code"] for item in departments}
    return by_code, by_name


def resolve_department(value, departments):
    by_code, by_name = lookup_codes(departments)
    text = str(value or "").strip()
    code = text.upper()
    if code in by_code:
        return by_code[code]
    if text.isdigit() and len(text) <= 3:
        padded = f"{int(text):02d}" if int(text) < 100 else str(int(text))
        return by_code.get(padded, "")
    if normalize(text) in by_name:
        return by_name[normalize(text)]
    match = re.search(r"\((\d{2,3}|2[AB])\)\s*$", code)
    if match:
        return by_code.get(match.group(1), "")
    return ""

async def async_get_departments(hass):
    """Read cached departments, updating weekly from the official API.

    Never discard a previously validated registry after an HTTP failure.
    """
    from datetime import datetime, timedelta, timezone
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.storage import Store
    import asyncio

    key = "_geo_departments"
    if key in hass.data.get(DOMAIN, {}):
        return hass.data[DOMAIN][key]
    store = Store(hass, 1, STORAGE_GEO_KEY)
    cached = await store.async_load() or {}
    records = cached.get("departments", [])
    checked = cached.get("checked_at")
    fresh = False
    if checked and records:
        try:
            fresh = datetime.fromisoformat(checked) > datetime.now(timezone.utc) - timedelta(days=7)
        except ValueError:
            pass
    if not fresh:
        try:
            async with asyncio.timeout(25):
                async with async_get_clientsession(hass).get(GEO_DEPARTMENTS_API_URL) as response:
                    response.raise_for_status()
                    payload = await response.json()
            records = validate_departments(payload)
            await store.async_save({"departments": records, "checked_at": datetime.now(timezone.utc).isoformat()})
        except Exception:
            if not records:
                raise
    records = validate_departments(records)
    hass.data.setdefault(DOMAIN, {})[key] = records
    return records
