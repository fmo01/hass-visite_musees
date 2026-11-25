"""Guard against scattered endpoints and accidental domain regressions."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "visite_musees"


def test_identity_and_version():
    manifest = json.loads((COMPONENT / 'manifest.json').read_text())
    assert manifest['domain'] == 'visite_musees'
    assert manifest['version'] == '0.1.12'
    assert (COMPONENT / 'frontend' / 'visite-musees-panel.js').exists()


def test_all_endpoint_origins_only_in_constants():
    constants = (COMPONENT / 'const.py').read_text()
    for origin in ('tabular-api.data.gouv.fr', 'geo.api.gouv.fr', 'www.data.gouv.fr',
                   'opendata.paris.fr', 'madparis.fr', 'www.musee-orsay.fr'):
        assert origin in constants
        for f in COMPONENT.glob('*.py'):
            if f.name != 'const.py':
                assert origin not in f.read_text(), f


def test_renamed_domain_has_no_legacy_reference():
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.py','.js','.json','.md'):
            body = path.read_text()
            assert ('paris' + '_musees') not in body
            assert ('paris' + '-musees') not in body
