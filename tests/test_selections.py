"""Pure helper and persistent storage tests without requiring Home Assistant."""
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "visite_musees"


def load_selection_module():
    # Minimal HA Store stub: tests persistence contract independently of HA runtime.
    ha = types.ModuleType("homeassistant")
    helpers = types.ModuleType("homeassistant.helpers")
    storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        state = {}

        def __init__(self, hass, version, key):
            self.key = key

        async def async_load(self):
            return self.state.get(self.key)

        async def async_save(self, data):
            self.state[self.key] = {k: dict(v) for k, v in data.items()}

    storage.Store = Store
    sys.modules.update({"homeassistant": ha, "homeassistant.helpers": helpers,
                        "homeassistant.helpers.storage": storage})
    pkg = sys.modules.setdefault("vm_selection_tests", types.ModuleType("vm_selection_tests"))
    pkg.__path__ = [str(ROOT)]
    spec = importlib.util.spec_from_file_location("vm_selection_tests.selections", ROOT / "selections.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stable_id_case_accents_and_start_date():
    mod = load_selection_module()
    a = {"museum_id": "orsay", "title": "Été au Musée", "start": "2026-11-01"}
    b = {"museum_id": "orsay", "title": "Ete au musee", "start": "2026-12-01"}
    assert mod.event_id(a) == mod.event_id(b)
    assert mod.event_id(a) != mod.event_id({**a, "museum_id": "mad"})


def test_saved_hidden_persist_restart_and_restore():
    mod = load_selection_module()
    a = {"museum_id": "mad", "title": "Exposition test", "start": "2026-11-01",
         "end": "2027-02-01", "source": "official_mad"}

    async def check():
        store = mod.SelectionStore(None, "entry_test")
        await store.async_load()
        eid = await store.async_set("saved", a, True)
        await store.async_set("hidden", a, True)
        restarted = mod.SelectionStore(None, "entry_test")
        await restarted.async_load()
        assert eid in restarted.serialized()["saved"]
        assert eid in restarted.serialized()["hidden"]
        await restarted.async_set("hidden", a, False)
        assert eid not in restarted.serialized()["hidden"]
        assert eid in restarted.serialized()["saved"]
        await restarted.async_set("saved", a, False)
        assert eid not in restarted.serialized()["saved"]

    asyncio.run(check())


def test_visit_history_survives_restarts_and_is_independent_from_saved():
    mod = load_selection_module()
    a = {"museum_id": "orsay", "title": "Visite historique", "start": "2026-11-01",
         "end": "2027-02-01", "url": "https://www.musee-orsay.fr/fr/"}

    async def check():
        store = mod.SelectionStore(None, "visit_history")
        await store.async_load()
        eid = await store.async_set_visit(a, "2026-12-05", False)
        assert store.serialized()["visits"][eid]["visited"] is False
        await store.async_set_visit(a, "2026-12-06", True)
        await store.async_set("saved", a, True)
        restarted = mod.SelectionStore(None, "visit_history")
        await restarted.async_load()
        record = restarted.serialized()["visits"][eid]
        assert record["visit_date"] == "2026-12-06"
        assert record["visited"] is True
        assert record["title"] == "Visite historique"
        await restarted.async_set("saved", a, False)
        assert eid in restarted.serialized()["visits"]
        await restarted.async_set_visit(a, None, False)
        assert eid not in restarted.serialized()["visits"]

    asyncio.run(check())


def test_invalid_visit_dates_do_not_overwrite_history():
    mod = load_selection_module()
    a = {"museum_id": "mad", "title": "Une exposition"}

    async def check():
        store = mod.SelectionStore(None, "invalid_dates")
        await store.async_set_visit(a, "2026-11-21", False)
        for bad in ("2026-02-30", "21/11/2026", "tomorrow"):
            try:
                await store.async_set_visit(a, bad, True)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid date was accepted")
        assert list(store.serialized()["visits"].values())[0]["visit_date"] == "2026-11-21"

    asyncio.run(check())
