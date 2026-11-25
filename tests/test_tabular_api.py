"""Test national Muséofile API response shape and all-pages handling."""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'visite_musees'
pkg = sys.modules.setdefault('pm_registry_tests', types.ModuleType('pm_registry_tests'))
pkg.__path__ = [str(ROOT)]
spec = importlib.util.spec_from_file_location('pm_registry_tests.museum_registry', ROOT / 'museum_registry.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.set_geo_departments([
    {"code": "75", "nom": "Paris", "codeRegion": "11"},
    {"code": "45", "nom": "Loiret", "codeRegion": "24"},
    {"code": "67", "nom": "Bas-Rhin", "codeRegion": "44"},
    {"code": "77", "nom": "Seine-et-Marne", "codeRegion": "11"},
    {"code": "13", "nom": "Bouches-du-Rhône", "codeRegion": "93"},
    {"code": "2A", "nom": "Corse-du-Sud", "codeRegion": "94"},
    {"code": "971", "nom": "Guadeloupe", "codeRegion": "01"},
])


def test_metadata_rid_and_json_catalogue():
    rid = 'a2c8fe89-0b3a-45d4-9fbc-18f9984b9b00'
    assert mod.select_resource({'resources': [{'id': rid, 'format': 'csv', 'type': 'main'}]}) == [rid]
    assert mod.tabular_url(rid).endswith('/api/resources/' + rid + '/data/')
    rows = [
        {'__id': 1, 'Identifiant': 'M5031', 'Nom_officiel': 'Musée du Louvre', 'Departement': 'Paris', 'Ville': 'Paris', 'URL': 'https://www.louvre.fr'},
        {'__id': 2, 'Identifiant': 'M0002', 'Nom_officiel': 'Musée fictif', 'Departement': 'Loiret', 'Ville': 'Orléans'},
    ]
    catalogue = mod.parse_json_catalogue(rows)
    assert len(catalogue) == 2
    assert catalogue[0]['department'] == '75'
    assert len(mod.filter_departments(catalogue, ['45'])) == 1


def test_empty_and_missing_json_are_rejected():
    import pytest
    with pytest.raises(ValueError, match='aucun musée'):
        mod.parse_json_catalogue([{'foo': 'bar'}])
    with pytest.raises(ValueError, match='liste'):
        mod.parse_json_catalogue({'data': []})
    with pytest.raises(ValueError):
        mod.tabular_url('not-a-uuid')


def test_no_csv_download_in_coordinator():
    text = (ROOT / 'coordinator.py').read_text()
    assert 'parse_catalogue' not in text
    assert 'raw_csv' not in text
    assert 'tabular_url(resource_id)' in text
    assert 'page_size' in text
    assert 'national_registry' in text


def test_two_page_download_and_incomplete_page_rejection():
    """Exercise the actual async collector method without importing HA."""
    import ast
    import pytest
    source = (ROOT / 'coordinator.py').read_text()
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'VisiteMuseesCoordinator')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_async_fetch_tabular_resource')
    code = compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<collector>', 'exec')
    scope = {'asyncio': asyncio, 'tabular_url': mod.tabular_url, 'parse_json_catalogue': mod.parse_json_catalogue}
    exec(code, scope)
    collector = scope['_async_fetch_tabular_resource']

    class Response:
        def __init__(self, data): self.data = data
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def raise_for_status(self): pass
        async def json(self, **kwargs): return self.data

    class Session:
        def __init__(self, pages): self.pages = pages; self.calls = []
        def get(self, url, params):
            self.calls.append((url, params))
            return Response(self.pages[params['page']])

    row1 = {'Identifiant':'M1', 'Nom_officiel':'Musée A','Departement':'Paris'}
    row2 = {'Identifiant':'M2', 'Nom_officiel':'Musée B','Departement':'Loiret'}
    good = Session({
        1: {'data':[row1], 'meta':{'total':2}, 'links':{'next':'some-next-url'}},
        2: {'data':[row2], 'meta':{'total':2}, 'links':{'next':None}},
    })
    rid = 'a2c8fe89-0b3a-45d4-9fbc-18f9984b9b00'
    result = asyncio.run(collector(None, good, rid))
    assert len(result) == 2
    assert [call[1]['page'] for call in good.calls] == [1,2]
    assert all(call[0] == mod.tabular_url(rid) for call in good.calls)

    broken = Session({1: {'data':[row1], 'meta':{'total':2}, 'links':{'next':None}}})
    with pytest.raises(ValueError, match='incomplètes'):
        asyncio.run(collector(None, broken, rid))
