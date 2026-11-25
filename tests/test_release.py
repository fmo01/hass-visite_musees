from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "visite_musees"

def test_release_version():
    assert json.loads((ROOT / "manifest.json").read_text())["version"] == "0.1.12"

def test_museum_read_is_not_in_constructor():
    source = (ROOT / "coordinator.py").read_text()
    constructor = source.split("def __init__", 1)[1].split("async def _async_update_data", 1)[0]
    assert "read_text(" not in constructor
    assert "parse_json_catalogue" in source
    assert "async_add_executor_job" not in source

def test_panel_registered_before_refresh():
    source = (ROOT / "__init__.py").read_text()
    assert source.index("await panel_custom.async_register_panel(") < source.index("await coordinator.async_refresh()")

def test_translations_and_visit_endpoint():
    for lang in ('fr','en','es'):
        assert 'config' in json.loads((ROOT / 'translations' / f'{lang}.json').read_text())
    websocket=(ROOT / 'websocket.py').read_text()
    assert 'WS_PREFIX}/visit' in websocket
    assert 'ws_visit' in websocket


def test_frontend_i18n_is_modular():
    panel = (ROOT / "frontend/visite-musees-panel.js").read_text()
    i18n = (ROOT / "frontend/i18n.js").read_text()
    init = (ROOT / "__init__.py").read_text()
    assert "from './i18n.js'" in panel
    assert "const translations =" not in panel
    assert "export function normalizeLanguage" in i18n
    assert "loadTranslations" in i18n
    assert "frontend/translations" in init or "FRONTEND_TRANSLATIONS_URL" in init
    assert "export function translate" in i18n
    assert "StaticPathConfig(I18N_MODULE_URL" in init
    assert "hass.locale?.language||hass.language" in panel


def test_frontend_language_files_and_manifest_version_banner():
    panel = (ROOT / 'frontend' / 'visite-musees-panel.js').read_text()
    init = (ROOT / '__init__.py').read_text()
    for language in ('fr', 'en', 'es'):
        data = json.loads((ROOT / 'frontend' / 'translations' / f'{language}.json').read_text())
        assert data['title']
        assert data['planned'] and data['visited']
    assert 'new URL(import.meta.url).searchParams.get' in panel
    assert 'console.info' in panel
    assert 'FRONTEND_TRANSLATIONS_URL' in init
    assert '.card.visit-planned' in panel and '.card.visit-visited' in panel
