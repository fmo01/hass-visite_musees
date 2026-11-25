"""Offline tests for national Muséofile parsing and filtering."""
import importlib.util
import sys
import types
from pathlib import Path
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


def test_parse_national_and_departments():
    sample = 'REF;NOMOFF;AUTNOM;DPT;VILLE_M;CP_M;ADRL1_M;URL_M\n'
    sample += 'M001;Musée d’Orsay;;75;Paris;75007;1 rue de la Légion d’honneur;https://www.musee-orsay.fr\n'
    sample += 'M002;Musée exemple;Autre nom;45;Orléans;45000;2 rue exemple;example.org\n'
    sample += 'M003;Musée Corse;;2A;Ajaccio;20000;3 rue exemple;\n'
    results = mod.parse_catalogue(sample.encode('utf-8-sig'))
    assert len(results) == 3
    assert results[0]['id'] == 'museofile_m001'
    assert results[0]['department'] == '75'
    assert results[1]['aliases'] == ['Autre nom']
    assert [m['department'] for m in mod.filter_departments(results, ['45','2A'])] == ['45','2A']


def test_resource_and_no_curated_merge():
    assert mod.select_resource({'resources':[{'id':'a2c8fe89-0b3a-45d4-9fbc-18f9984b9b00','format':'csv','url':'https://example.org/file.csv'}]}) == ['a2c8fe89-0b3a-45d4-9fbc-18f9984b9b00']
    assert mod.department_code('075') == '75'
    assert mod.department_code('971') == '971'
    assert mod.parse_museum({'REF':'','NOMOFF':'Musée', 'DPT':'75'}) is None
    assert not (ROOT/'museums.json').exists()


def test_csv_delimiter_even_with_text_commas():
    csv_text = ('REF;NOMOFF;DPT;VILLE_M;HIST\n'
                'M0001;Musée de France, histoire et arts;75;Paris;"Texte, avec beaucoup, de virgules"\n')
    entries = mod.parse_catalogue(csv_text.encode('utf-8-sig'))
    assert len(entries) == 1
    assert entries[0]['department'] == '75'


def test_csv_bad_header_diagnostic():
    import pytest
    with pytest.raises(ValueError, match='header not recognized'):
        mod.parse_catalogue(b'not_a_real_file;hello\na;b\n')


def test_legacy_cache_entries_do_not_crash():
    items = [{'id': 'old', 'name': 'Old'}, {'id': 'museofile_m1', 'name': 'Musée', 'department': '75'}]
    assert [m['id'] for m in mod.filter_departments(items, ['75'])] == ['museofile_m1']


def test_coordinator_uses_new_cache_key_only():
    source = (ROOT / 'coordinator.py').read_text()
    assert 'filter_departments(cache.get("national_registry", [])' in source
    assert 'filter_departments(cache.get("museum_registry", [])' not in source


def test_actual_national_export_pipe_header():
    sample = (
        'Identifiant|Nom_officiel|Adresse|Lieu|Code_postal|Ville|Departement|Region|URL|Telephone|Categorie|Domaine_thematique|Histoire|Atout|Themes|\n'
        'M001|Musée d’Orsay|1 rue de la Légion d’honneur||75007|Paris|75|Île-de-France|https://www.musee-orsay.fr|||||||\n'
        'M002|Musée des Beaux-Arts|Rue Exemple||45000|Orléans|45|Centre-Val de Loire||||||||\n'
    )
    result = mod.parse_catalogue(sample.encode('utf-8-sig'))
    assert len(result) == 2
    assert result[0]['department'] == '75'
    assert result[0]['name'] == 'Musée d’Orsay'
    assert result[0]['museofile_ref'] == 'M001'
    assert [m['id'] for m in mod.filter_departments(result, ['75'])] == ['museofile_m001']


def test_mixed_header_variants():
    text = 'Identifiant,Nom_officiel,DPT,Ville\nM3,Musée Exemple,75,Paris\n'
    assert len(mod.parse_catalogue(text)) == 1


def test_actual_museofile_csv_named_departments():
    raw = (
        "Identifiant|Nom_officiel|Adresse|Lieu|Code_postal|Ville|Departement|Region|URL|Telephone\n"
        "M5031|musée du Louvre|rue de Rivoli||75001|Paris|Paris|Ile-de-France|www.louvre.fr|\n"
        "M0002|musée de test|rue X||45000|Orléans|Loiret|Centre-Val de Loire||\n"
        "M0003|musée alsacien|rue Y||67000|Strasbourg|Bas-Rhin|Grand Est||\n"
    ).encode("utf-8")
    museums = mod.parse_catalogue(raw)
    assert len(museums) == 3
    assert {m["department"] for m in museums} == {"75", "45", "67"}
    assert len(mod.filter_departments(museums, ["75"])) == 1
    assert len(mod.filter_departments(museums, ["75", "45"])) == 2

def test_department_name_and_code_equivalence():
    assert mod.department_code("Paris") == "75"
    assert mod.department_code("Seine-et-Marne") == "77"
    assert mod.department_code("Bouches-du-Rhône") == "13"
    assert mod.department_code("Corse-du-Sud") == "2A"
    assert mod.department_code("Guadeloupe") == "971"
