# =============================================================================
# official_sources.py - Komunikaty ze źródeł rządowych/official (G20, banki centralne)
# Selektywne filtrowanie: tylko treści mogące wpływać na rynek (stopy, sankcje, handel, surowce).
# =============================================================================

import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_SCRIPT_DIR, "data", "official_headlines.db")

# Słowa kluczowe – tylko takie komunikaty trafiają do raportu/dashboardu
KEYWORDS_MARKET_RELEVANT = [
    "rate", "interest", "fed", "ecb", "boe", "central bank", "inflation",
    "sanctions", "trade", "tariff", "oil", "gas", "opec", "stimulus",
    "debt", "default", "gdp", "employment", "nfp", "cpi", "fomc",
    "stopy", "procent", "sankcje", "handel", "ropa", "gaz", "dług",
]
KEYWORDS_PL = [re.compile(r"\b" + re.escape(w) + r"\b", re.I) for w in "stopy procent sankcje handel ropa gaz dług inflacja fomc nbp ecb".split()]

# Źródła RSS (URL, nazwa, krótki opis)
OFFICIAL_FEEDS = [
    {"url": "https://www.ecb.europa.eu/rss/press.html", "name": "ECB", "region": "EU"},
    {"url": "https://www.federalreserve.gov/feeds/press_all.xml", "name": "Federal Reserve", "region": "USA"},
    {"url": "https://www.bankofengland.co.uk/rss/news", "name": "Bank of England", "region": "UK"},
    {"url": "https://www.nbpr.pl/rss/informacje.xml", "name": "NBP", "region": "PL"},
]
# Biały Dom / Treasury – często mają RSS; Kreml zwykle nie w prostym RSS. Dodaj więcej w config jeśli potrzeba.
try:
    from config import OFFICIAL_FEEDS_EXTRA
except ImportError:
    OFFICIAL_FEEDS_EXTRA = []


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS official_headlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                region TEXT,
                title TEXT NOT NULL,
                link TEXT,
                published TEXT,
                fetched_at TEXT NOT NULL,
                is_relevant INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_official_fetched ON official_headlines(fetched_at DESC)")


def _is_relevant(title: str, description: str = "") -> bool:
    """Czy komunikat może mieć wpływ na rynek (stopy, sankcje, handel, ropa...)."""
    text = (title + " " + (description or "")).lower()
    for kw in KEYWORDS_MARKET_RELEVANT:
        if kw.lower() in text:
            return True
    for pat in KEYWORDS_PL:
        if pat.search(text):
            return True
    return False


def _fetch_rss(url: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """Pobiera RSS i zwraca listę {title, link, published, description}."""
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "SofikaMax-Agent/1.0"})
        if r.status_code != 200:
            return []
    except Exception:
        return []
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        items = []
        for item in root.iter("item"):
            title = (item.find("title") or item.find("{http://purl.org/rss/1.0/}title"))
            link = (item.find("link") or item.find("{http://purl.org/rss/1.0/}link"))
            pub = (item.find("pubDate") or item.find("published") or item.find("{http://purl.org/dc/elements/1.1/}date"))
            desc = (item.find("description") or item.find("{http://purl.org/rss/1.0/}description"))
            t = title.text.strip() if title is not None and title.text else ""
            l = link.text.strip() if link is not None and link.text else ""
            p = pub.text.strip() if pub is not None and pub.text else ""
            d = (desc.text or "").strip() if desc is not None else ""
            if t:
                items.append({"title": t[:300], "link": l, "published": p, "description": d[:500]})
        return items[:20]
    except Exception:
        return []


def fetch_and_store(max_age_hours: int = 24) -> int:
    """
    Pobiera nagłówki z OFFICIAL_FEEDS + OFFICIAL_FEEDS_EXTRA, filtruje po słowach kluczowych,
    zapisuje do DB. Zwraca liczbę zapisanych wpisów.
    """
    _init_db()
    try:
        extra = getattr(__import__("config", fromlist=["OFFICIAL_FEEDS_EXTRA"]), "OFFICIAL_FEEDS_EXTRA", [])
    except Exception:
        extra = []
    feeds = OFFICIAL_FEEDS + (extra or [])
    count = 0
    fetched_at = datetime.now().isoformat()
    with _conn() as conn:
        for feed in feeds:
            url = feed.get("url", "")
            name = feed.get("name", "Official")
            region = feed.get("region", "")
            items = _fetch_rss(url)
            for it in items:
                if not _is_relevant(it.get("title", ""), it.get("description", "")):
                    continue
                try:
                    conn.execute(
                        """INSERT INTO official_headlines (source, region, title, link, published, fetched_at, is_relevant)
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (name, region, it.get("title", ""), it.get("link", ""), it.get("published", ""), fetched_at),
                    )
                    count += 1
                except Exception:
                    pass
        conn.commit()
    return count


def get_latest(limit: int = 25, region: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ostatnie komunikaty (z bazy). region=None = wszystkie."""
    _init_db()
    with _conn() as conn:
        if region:
            rows = conn.execute(
                """SELECT source, region, title, link, published, fetched_at
                   FROM official_headlines WHERE is_relevant = 1 AND region = ?
                   ORDER BY fetched_at DESC LIMIT ?""",
                (region, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT source, region, title, link, published, fetched_at
                   FROM official_headlines WHERE is_relevant = 1
                   ORDER BY fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_summary_for_report(max_items: int = 5) -> str:
    """Krótkie podsumowanie do raportu PDF / narracji (np. 1–2 zdania)."""
    items = get_latest(limit=max_items)
    if not items:
        return ""
    parts = [f"{i['source']}: {i['title'][:60]}…" for i in items[:3]]
    return "Komunikaty oficjalne (wybrane): " + " | ".join(parts)
