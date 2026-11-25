"""Experimental parsers for official exhibition listings: no invented dates."""
from __future__ import annotations
import json
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup

MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
          "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
          "octobre": 10, "novembre": 11, "decembre": 12}
DATE = re.compile(r"(?<!\d)(\d{1,2})\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+(20\d{2})", re.I)
ISO = re.compile(r"^\d{4}-\d\d-\d\d")

def ascii_text(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c)).lower()

def dates_in(text):
    out = []
    for m in DATE.finditer(ascii_text(text)):
        try:
            out.append(date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat())
        except ValueError:
            pass
    return out

def item(mid, title, start, end, url, source):
    if not title or not ISO.match(str(start)) or not ISO.match(str(end)):
        return None
    if date.fromisoformat(start[:10]) > date.fromisoformat(end[:10]):
        return None
    return {"museum_id":mid,"title":title.strip(),"start":start[:10],"end":end[:10],
            "url":url,"image":None,"price_type":None,"source":source,
            "verified_at":date.today().isoformat()}

def jsonld_events(soup, mid, url):
    found=[]
    def nodes(value):
        if isinstance(value, list):
            for elem in value: yield from nodes(elem)
        elif isinstance(value, dict):
            yield value
            if "@graph" in value: yield from nodes(value["@graph"])
    for tag in soup.select('script[type="application/ld+json"]'):
        try: document=json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError): continue
        for node in nodes(document):
            types=node.get('@type', [])
            types=[types] if isinstance(types, str) else types
            if not any('ExhibitionEvent' in str(t) or 'Event' == str(t) for t in types): continue
            start=str(node.get('startDate',''))[:10]; end=str(node.get('endDate',''))[:10]
            entry=item(mid, str(node.get('name','')), start, end,
                       str(node.get('url') or url), f'official_{mid}')
            if entry: found.append(entry)
    return found

def official_exhibitions(html, mid, url):
    """Conservative extraction: only explicit date pairs from listing cards."""
    soup=BeautifulSoup(html, 'html.parser')
    found=jsonld_events(soup, mid, url)
    # Do not mistake guided tours for exhibitions. Cards must have date range and title.
    for card in soup.select('article, .views-row, .card, .item-list > li, .expo, .exposition'):
        title_tag=card.find(['h2','h3','h4'])
        if not title_tag: continue
        title=title_tag.get_text(' ', strip=True)
        if len(title)<5 or len(title)>180: continue
        text=card.get_text(' ', strip=True)
        dates=dates_in(text)
        if len(dates)<2: continue
        link=title_tag.find('a') or card.find('a',href=True)
        link_url=urljoin(url,link.get('href','')) if link else url
        entry=item(mid,title,dates[0],dates[1],link_url,f'official_{mid}')
        if entry: found.append(entry)
    if mid == "mad":
        # MAD uses listing elements that do not consistently carry article/card
        # class names. Inspect short, local link containers instead of relying
        # on site-specific CSS selectors; never infer dates.
        for link in soup.select("a[href]"):
            title = link.get_text(" ", strip=True)
            if not 8 <= len(title) <= 150:
                continue
            for parent in list(link.parents)[:4]:
                if parent.name in ("html", "body"):
                    break
                text = parent.get_text(" ", strip=True)
                if not 25 <= len(text) <= 700:
                    continue
                # Avoid interpreting navigation and ticket links as exhibitions.
                if ascii_text(title) not in ascii_text(text[:200]):
                    continue
                dates = dates_in(text)
                if len(dates) != 2:
                    continue
                entry = item(mid, title, dates[0], dates[1],
                             urljoin(url, link.get("href", "")), f"official_{mid}")
                if entry:
                    found.append(entry)
                    break
    return list({(e['museum_id'],ascii_text(e['title']),e['start']):e for e in found}.values())
