# =============================================================================
# history_archive.py - Centralne archiwum historii dla wszystkich warstw
# Dla AI (np. Cuade): szybki odczyt "co było" – FRED, flow ETF, regime weekly, news, events.
#
# API dla AI (Cuade):
#   get_available_sources()     -> dict: fred_series[], flow_tickers[], regime_tickers[], news_instruments[], events_count
#   get_history_fred(id, limit) -> DataFrame(date, value)
#   get_history_flow(ticker, days) -> DataFrame(date, Open, High, Low, Close, Volume)
#   get_history_regime(ticker, weeks) -> DataFrame (weekly OHLC; ticker = EUR, GBP, ...)
#   get_history_news(instrument, days) -> DataFrame(obs_date, nps, headline_count, bias, top_headline)
#   get_history_events(currency?, from_date?, to_date?, limit) -> list[dict]
# Baza: history.db (SQLite w katalogu projektu).
# =============================================================================

import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

HISTORY_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


def _conn():
    return sqlite3.connect(HISTORY_DB)


def init_archive():
    """Tworzy tabele: fred_series, flow_ohlc, regime_ohlc, news_daily, events."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS fred_series (
                series_id TEXT NOT NULL,
                obs_date TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT,
                PRIMARY KEY (series_id, obs_date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_fred_series ON fred_series(series_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fred_date ON fred_series(obs_date)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS flow_ohlc (
                ticker TEXT NOT NULL,
                obs_date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                created_at TEXT,
                PRIMARY KEY (ticker, obs_date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_flow_ticker ON flow_ohlc(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_flow_date ON flow_ohlc(obs_date)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS regime_ohlc (
                ticker TEXT NOT NULL,
                obs_date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                created_at TEXT,
                PRIMARY KEY (ticker, obs_date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_regime_ticker ON regime_ohlc(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_regime_date ON regime_ohlc(obs_date)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS news_daily (
                instrument TEXT NOT NULL,
                obs_date TEXT NOT NULL,
                nps REAL, headline_count INTEGER, bias TEXT, top_headline TEXT,
                created_at TEXT,
                PRIMARY KEY (instrument, obs_date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_news_inst ON news_daily(instrument)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_news_date ON news_daily(obs_date)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                currency TEXT NOT NULL,
                event_name TEXT NOT NULL,
                impact TEXT,
                forecast TEXT, previous TEXT, actual TEXT,
                created_at TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_currency ON events(currency)")


# -----------------------------------------------------------------------------
# FRED (macro, surprise, cycle używają FRED)
# -----------------------------------------------------------------------------

def upsert_fred(series_id: str, df: pd.DataFrame) -> int:
    """Zapisuje obserwacje FRED. df: kolumny date, value."""
    if df is None or len(df) == 0:
        return 0
    init_archive()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for _, row in df.iterrows():
        dt = row.get("date")
        if pd.isna(dt):
            continue
        obs_date = pd.Timestamp(dt).strftime("%Y-%m-%d")
        val = row.get("value")
        if pd.isna(val):
            continue
        rows.append((series_id, obs_date, float(val), now))
    if not rows:
        return 0
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO fred_series (series_id, obs_date, value, created_at) VALUES (?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_history_fred(series_id: str, limit: int = 500) -> Optional[pd.DataFrame]:
    """Odczyt historii FRED. Zwraca DataFrame: date, value (sortowane rosnąco)."""
    init_archive()
    with _conn() as c:
        rows = c.execute(
            "SELECT obs_date, value FROM fred_series WHERE series_id = ? ORDER BY obs_date DESC LIMIT ?",
            (series_id, limit),
        ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["obs_date", "value"])
    df["date"] = pd.to_datetime(df["obs_date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    return df[["date", "value"]]


# -----------------------------------------------------------------------------
# Flow (ETF daily OHLC)
# -----------------------------------------------------------------------------

def _df_ohlc_to_rows(ticker: str, df: pd.DataFrame) -> list:
    """Konwertuje DataFrame yfinance (index = daty, kolumny Open/High/Low/Close/Volume) na wiersze do INSERT."""
    if df is None or df.empty:
        return []
    df = df.copy()
    if "Date" not in df.columns and hasattr(df.index, "date"):
        df = df.reset_index()
    rows = []
    for idx, row in df.iterrows():
        dt = row.get("Date", None) if "Date" in df.columns else (idx if hasattr(idx, "strftime") else None)
        if dt is None:
            continue
        obs_date = pd.Timestamp(dt).strftime("%Y-%m-%d")
        o = row.get("Open")
        h = row.get("High")
        l = row.get("Low")
        c = row.get("Close")
        v = row.get("Volume")
        if pd.isna(c):
            continue
        rows.append((ticker, obs_date, float(o) if not pd.isna(o) else None, float(h) if not pd.isna(h) else None,
                     float(l) if not pd.isna(l) else None, float(c), float(v) if not pd.isna(v) and v else None,
                     datetime.now().strftime("%Y-%m-%d %H:%M")))
    return rows


def upsert_flow_ohlc(ticker: str, df: pd.DataFrame) -> int:
    """Zapisuje daily OHLC dla ETF (flow). df: yfinance format (Open, High, Low, Close, Volume)."""
    rows = _df_ohlc_to_rows(ticker, df)
    if not rows:
        return 0
    init_archive()
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO flow_ohlc (ticker, obs_date, open, high, low, close, volume, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_history_flow(ticker: str, days: int = 252) -> Optional[pd.DataFrame]:
    """Odczyt historii flow (daily). Zwraca DataFrame z kolumnami date, Open, High, Low, Close, Volume."""
    init_archive()
    with _conn() as c:
        rows = c.execute(
            "SELECT obs_date, open, high, low, close, volume FROM flow_ohlc WHERE ticker = ? ORDER BY obs_date DESC LIMIT ?",
            (ticker, days),
        ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["obs_date", "Open", "High", "Low", "Close", "Volume"])
    df["date"] = pd.to_datetime(df["obs_date"])
    return df.sort_values("date").reset_index(drop=True)


# -----------------------------------------------------------------------------
# Regime (weekly OHLC per waluta)
# -----------------------------------------------------------------------------

def upsert_regime_ohlc(ticker: str, df: pd.DataFrame) -> int:
    """Zapisuje weekly OHLC (regime). ticker = symbol waluty (EUR, GBP, ...). df: yfinance weekly."""
    rows = _df_ohlc_to_rows(ticker, df)
    if not rows:
        return 0
    init_archive()
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO regime_ohlc (ticker, obs_date, open, high, low, close, volume, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_history_regime(ticker: str, weeks: int = 156) -> Optional[pd.DataFrame]:
    """Odczyt historii regime (weekly)."""
    init_archive()
    with _conn() as c:
        rows = c.execute(
            "SELECT obs_date, open, high, low, close, volume FROM regime_ohlc WHERE ticker = ? ORDER BY obs_date DESC LIMIT ?",
            (ticker, weeks),
        ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["obs_date", "Open", "High", "Low", "Close", "Volume"])
    df["date"] = pd.to_datetime(df["obs_date"])
    return df.sort_values("date").reset_index(drop=True)


# -----------------------------------------------------------------------------
# News (daily snapshot sentymentu per instrument)
# -----------------------------------------------------------------------------

def upsert_news_daily(instrument: str, obs_date: str, nps: float, headline_count: int = 0, bias: str = "", top_headline: str = "") -> int:
    init_archive()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO news_daily (instrument, obs_date, nps, headline_count, bias, top_headline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (instrument, obs_date[:10], nps, headline_count, bias[:50] if bias else "", (top_headline or "")[:500], now),
        )
    return 1


def get_history_news(instrument: str, days: int = 90) -> Optional[pd.DataFrame]:
    init_archive()
    with _conn() as c:
        rows = c.execute(
            "SELECT obs_date, nps, headline_count, bias, top_headline FROM news_daily WHERE instrument = ? ORDER BY obs_date DESC LIMIT ?",
            (instrument, days),
        ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["obs_date", "nps", "headline_count", "bias", "top_headline"])
    df["date"] = pd.to_datetime(df["obs_date"])
    return df.sort_values("date").reset_index(drop=True)


# -----------------------------------------------------------------------------
# Events (kalendarz ekonomiczny – przeszłe i przyszłe)
# -----------------------------------------------------------------------------

def upsert_events(events: List[Dict[str, Any]]) -> int:
    """Zapisuje wydarzenia (z kalendarza). Każdy: date, currency, event, impact, forecast, previous."""
    if not events:
        return 0
    init_archive()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for e in events:
        event_date = (e.get("date") or e.get("event_date") or "")[:10]
        currency = (e.get("currency") or "USD").upper()
        event_name = (e.get("event") or e.get("title") or e.get("event_name") or "")[:200]
        impact = (e.get("impact") or "medium")[:20]
        forecast = (e.get("forecast") or "")[:100]
        previous = (e.get("previous") or "")[:100]
        actual = (e.get("actual") or "")[:100]
        if not event_date or not event_name:
            continue
        rows.append((event_date, currency, event_name, impact, forecast, previous, actual, now))
    if not rows:
        return 0
    with _conn() as c:
        c.executemany(
            "INSERT INTO events (event_date, currency, event_name, impact, forecast, previous, actual, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_history_events(currency: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """Odczyt wydarzeń. currency=None = wszystkie."""
    init_archive()
    sql = "SELECT event_date, currency, event_name, impact, forecast, previous, actual FROM events WHERE 1=1"
    params = []
    if currency:
        sql += " AND currency = ?"
        params.append(currency.upper())
    if from_date:
        sql += " AND event_date >= ?"
        params.append(from_date[:10])
    if to_date:
        sql += " AND event_date <= ?"
        params.append(to_date[:10])
    sql += " ORDER BY event_date DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [
        {"event_date": r[0], "currency": r[1], "event_name": r[2], "impact": r[3], "forecast": r[4], "previous": r[5], "actual": r[6]}
        for r in rows
    ]


# -----------------------------------------------------------------------------
# API dla AI: co jest dostępne w archiwum
# -----------------------------------------------------------------------------

def get_available_sources() -> Dict[str, Any]:
    """Zwraca podsumowanie: jakie serie/tickery mają dane i w jakim zakresie dat. Dla Cuade AI."""
    init_archive()
    out = {"fred_series": [], "flow_tickers": [], "regime_tickers": [], "news_instruments": [], "events_count": 0}
    with _conn() as c:
        for row in c.execute("SELECT series_id, MIN(obs_date), MAX(obs_date), COUNT(*) FROM fred_series GROUP BY series_id"):
            out["fred_series"].append({"series_id": row[0], "from": row[1], "to": row[2], "count": row[3]})
        for row in c.execute("SELECT ticker, MIN(obs_date), MAX(obs_date), COUNT(*) FROM flow_ohlc GROUP BY ticker"):
            out["flow_tickers"].append({"ticker": row[0], "from": row[1], "to": row[2], "count": row[3]})
        for row in c.execute("SELECT ticker, MIN(obs_date), MAX(obs_date), COUNT(*) FROM regime_ohlc GROUP BY ticker"):
            out["regime_tickers"].append({"ticker": row[0], "from": row[1], "to": row[2], "count": row[3]})
        for row in c.execute("SELECT instrument, MIN(obs_date), MAX(obs_date), COUNT(*) FROM news_daily GROUP BY instrument"):
            out["news_instruments"].append({"instrument": row[0], "from": row[1], "to": row[2], "count": row[3]})
        row = c.execute("SELECT COUNT(*) FROM events").fetchone()
        out["events_count"] = row[0] if row else 0
    return out
