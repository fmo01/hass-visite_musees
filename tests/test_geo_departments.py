"""Validate the API Géo contract without requiring Home Assistant or network."""
import importlib.util
import sys
import types
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "visite_musees"
pkg = sys.modules.setdefault("vm_geo_tests", types.ModuleType("vm_geo_tests"))
pkg.__path__ = [str(ROOT)]
spec = importlib.util.spec_from_file_location("vm_geo_tests.geo_departments", ROOT / "geo_departments.py")
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


def test_official_departments_and_names():
    rows = [{"nom": f"Dept {i}", "code": f"{i:02d}", "codeRegion": "11"} for i in range(1, 96) if i != 20]
    rows += [{"nom": "Corse-du-Sud", "code": "2A", "codeRegion": "94"},
             {"nom": "Haute-Corse", "code": "2B", "codeRegion": "94"},
             {"nom": "Paris", "code": "75", "codeRegion": "11"},
             {"nom": "Guadeloupe", "code": "971", "codeRegion": "01"},
             {"nom": "La Réunion", "code": "974", "codeRegion": "04"}]
    result = geo.validate_departments(rows)
    assert geo.resolve_department("Paris", result) == "75"
    assert geo.resolve_department("075", result) == "75"
    assert geo.resolve_department("Corse-du-Sud", result) == "2A"
    assert geo.resolve_department("La Reunion", result) == "974"
    assert geo.resolve_department("Loiret", result) == ""  # never guess an unknown name
    assert geo.resolve_department("Paris (75)", result) == "75"


def test_incomplete_api_response_is_rejected():
    with pytest.raises(ValueError, match="incomplet"):
        geo.validate_departments([{"nom": "Paris", "code": "75", "codeRegion": "11"}])


def test_options_are_loaded_dynamically():
    text = (ROOT / "config_flow.py").read_text()
    assert "async_get_departments" in text
    assert "DEPARTMENT_CODES" not in text
    registry = (ROOT / "museum_registry.py").read_text()
    assert "DEPARTMENT_NAMES" not in registry
