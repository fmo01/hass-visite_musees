"""Run with pytest once BeautifulSoup is installed."""
import importlib.util
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "visite_musees" / "official.py"
spec=importlib.util.spec_from_file_location("official",ROOT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_card_dates():
    page = '<article><h2><a href="/expo">Une exposition</a></h2><p>Du 11 novembre 2026 au 21 mars 2027</p></article>'
    events=module.official_exhibitions(page,"mad","https://madparis.fr/Expositions-en-cours-501")
    assert len(events)==1
    assert events[0]['start']=='2026-11-11'
    assert events[0]['end']=='2027-03-21'

def test_no_date_is_not_invented():
    assert module.official_exhibitions('<article><h2>Sans date</h2></article>',"mad","https://madparis.fr/")==[]


def test_mad_listing_without_article_markup():
    page = (
        '<div class="listing"><div class="exhibition-entry">'
        '<a href="/expo-example">Rafael Pavarotti, photographe</a>'
        '<span>du 2 octobre 2026 au 2 mai 2027</span>'
        '</div></div>'
    )
    events = module.official_exhibitions(page, "mad", "https://madparis.fr/Expositions-en-cours-501")
    assert any(e["title"] == "Rafael Pavarotti, photographe" and
               e["start"] == "2026-10-02" and e["end"] == "2027-05-02"
               for e in events)

def test_mad_undated_links_are_ignored():
    page = '<div><a href="/exposition">Une exposition sans dates</a></div>'
    assert module.official_exhibitions(page,"mad","https://madparis.fr/") == []
