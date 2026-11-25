"""National Muséofile JSON catalogue through data.gouv.fr Tabular API."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from urllib.parse import urlparse

from .const import TABULAR_API_BASE_URL
DEFAULT_DEPARTMENTS = ["75"]
# Set from the official API Géo and reused by the museum parser.
# Codes are kept as strings to preserve leading zeros and Corsican codes.
from .geo_departments import resolve_department
_GEO_DEPARTMENTS = []


def set_geo_departments(departments):
    global _GEO_DEPARTMENTS
    _GEO_DEPARTMENTS = list(departments)


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c)).lower()).strip()


def department_code(value):
    return resolve_department(value, _GEO_DEPARTMENTS)


def select_resource(dataset):
    """Choose a published Muséofile resource ID for the tabular API.

    IDs come from the dataset metadata; never infer IDs from a download URL.
    """
    resources = dataset.get("resources", [])
    candidates = [
        r for r in resources
        if r.get("id") and str(r.get("format", "")).lower() in
        ("csv", "csv.gz", "xls", "xlsx", "parquet")
        and r.get("type", "main") in ("main", "primary")
    ]
    if not candidates:
        # Some publishers do not label their main resource's type.
        candidates = [
            r for r in resources
            if r.get("id") and str(r.get("format", "")).lower() in
            ("csv", "csv.gz", "xls", "xlsx", "parquet")
        ]
    candidates.sort(key=lambda r: (
        "museofile" not in (str(r.get("title", "")) + str(r.get("url", ""))).lower(),
        not r.get("is_available", True),
    ))
    if not candidates:
        raise ValueError("Aucune ressource Muséofile tabulaire identifiée")
    return [str(r["id"]) for r in candidates]


def tabular_url(resource_id):
    """Produce the API URL from a UUID-style resource ID."""
    import uuid
    return f"{TABULAR_API_BASE_URL}/{uuid.UUID(resource_id)}/data/"


def parse_json_catalogue(rows):
    """Normalize all API rows, refusing empty or malformed catalogues."""
    if not isinstance(rows, list):
        raise ValueError("Muséofile JSON: 'data' doit être une liste")
    museums = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        museum = parse_museum(row)
        if museum:
            museums[museum["id"]] = museum
    if not museums:
        raise ValueError("Muséofile JSON: aucun musée exploitable (identifiant, nom ou département manquant)")
    return list(museums.values())


def _url(value):
    value = str(value or "").strip()
    if value and not value.startswith(("https://", "http://")):
        value = "https://" + value
    parsed = urlparse(value)
    return value if parsed.scheme in ("http", "https") and parsed.netloc else ""


def parse_museum(row):
    """Normalize one official Muséofile row, with stable REF key."""
    r = {normalized(k).replace(" ", "_"): str(v or "").strip() for k, v in row.items() if k and isinstance(v, (str, int, float))}
    def field(*names):
        return next((r.get(name, "") for name in names if r.get(name)), "")
    ref = field("ref", "identifiant_du_musee", "identifiant")
    name = field("nomoff", "nom_officiel", "nom_officiel_du_musee")
    if not ref or not name:
        return None
    dept = department_code(field("dpt", "departement", "code_departement"))
    if not dept:
        return None
    city = field("ville_m", "ville", "commune")
    postal = field("cp_m", "code_postal", "cp")
    address = ", ".join(x for x in (field("adrl1_m", "adresse"), field("lieu_m"), " ".join(x for x in (postal, city) if x)) if x)
    aliases = [alias for alias in (field("autnom", "nomusage", "nom_usage"),) if alias and normalized(alias) != normalized(name)]
    return {
        "id": "museofile_" + normalized(ref).replace(" ", "_"),
        "museofile_ref": ref,
        "department": dept,
        "name": name,
        "aliases": aliases,
        "address": address,
        "url": _url(field("url_m", "url", "site_internet")),
        "city": city,
        "registry_source": "museofile_national",
    }


def _decode_csv(content):
    """Decode the national export, preserving a useful error for invalid data."""
    if isinstance(content, str):
        return content.lstrip("\ufeff")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Muséofile CSV: unsupported text encoding")


def parse_catalogue(content):
    """Read a national Muséofile export with validated header and separator.

    Do not rely on csv.Sniffer alone: semicolons in free-text descriptions
    and commas in addresses can mislead its heuristic.
    """
    text = _decode_csv(content)
    lines = text.splitlines(keepends=True)
    # Some CSV exports are preceded by a blank line or an Excel sep= hint.
    while lines and (not lines[0].strip() or lines[0].strip().lower().startswith("sep=")):
        lines.pop(0)
    if not lines:
        raise ValueError("Muséofile CSV is empty")
    header = lines[0]
    # Official published exports can use either legacy field names or
    # descriptive field names; validate logical fields, not exact spellings.
    required_groups = (
        {"REF", "IDENTIFIANT", "IDENTIFIANT_DU_MUSEE"},
        {"NOMOFF", "NOM_OFFICIEL", "NOM_OFFICIEL_DU_MUSEE"},
        {"DPT", "DEPARTEMENT", "CODE_DEPARTEMENT"},
    )
    candidates = []
    for delimiter in (";", ",", "\t", "|"):
        columns = [normalized(col).replace(" ", "_").upper() for col in next(csv.reader([header], delimiter=delimiter))]
        candidates.append((sum(bool(set(columns) & group) for group in required_groups), delimiter, columns))
    score, delimiter, columns = max(candidates, key=lambda item: item[0])
    if score != 3:
        raise ValueError("Muséofile CSV header not recognized (museum identifier/name/department missing): " + repr(header[:140]))
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter=delimiter)
    museums = {}
    for row in reader:
        museum = parse_museum(row)
        if museum:
            museums[museum["id"]] = museum
    if not museums:
        raise ValueError("Muséofile CSV has no usable museums (verify REF, NOMOFF, DPT values)")
    return list(museums.values())


def filter_departments(museums, departments):
    selected = {department_code(code) for code in departments}
    # The old cache used other keys. Skip those entries instead of failing
    # the entire Home Assistant refresh. Never merge them into Muséofile.
    return [museum for museum in museums
            if isinstance(museum, dict) and department_code(museum.get("department")) in selected
            and museum.get("id") and museum.get("name")]
