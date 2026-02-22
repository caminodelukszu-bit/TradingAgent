# =============================================================================
# cot_archive.py - Archiwum historycznych danych COT (26 tyg – 3 lata)
# AI i analiza ekstremów: "co było" i "gdzie jesteśmy vs historia".
# =============================================================================

import os
import sqlite3
import pandas as pd
from typing import Optional

COT_ARCHIVE_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cot_archive.db")


def _conn():
    return sqlite3.connect(COT_ARCHIVE_DB)


def init_archive():
    """Tabela: instrument, report_date (UNIQUE per instrument), net_position, net_change, oi, oi_change."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS cot_history (
                instrument TEXT NOT NULL,
                report_date TEXT NOT NULL,
                net_position REAL NOT NULL,
                net_change REAL,
                oi REAL,
                oi_change REAL,
                long_all REAL,
                short_all REAL,
                created_at TEXT,
                PRIMARY KEY (instrument, report_date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cot_inst_date ON cot_history(instrument, report_date)")


def upsert_cot_series(instrument: str, df: pd.DataFrame) -> int:
    """
    Zapisuje/aktualizuje serie COT do archiwum. df musi mieć: date, net_position, net_change, oi, oi_change.
    Zwraca liczbę wstawionych/zaktualizowanych wierszy.
    """
    if df is None or len(df) == 0:
        return 0
    init_archive()
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for _, row in df.iterrows():
        dt = row.get("date")
        if pd.isna(dt):
            continue
        report_date = pd.Timestamp(dt).strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        net = row.get("net_position")
        if pd.isna(net):
            continue
        net_change = row.get("net_change")
        oi = row.get("oi", 0)
        oi_change = row.get("oi_change", 0)
        long_all = row.get("long_all", None)
        short_all = row.get("short_all", None)
        rows.append((instrument.upper(), report_date, float(net), float(net_change) if not pd.isna(net_change) else None,
                     float(oi) if not pd.isna(oi) else None, float(oi_change) if not pd.isna(oi_change) else None,
                     float(long_all) if long_all is not None and not pd.isna(long_all) else None,
                     float(short_all) if short_all is not None and not pd.isna(short_all) else None, now))
    if not rows:
        return 0
    with _conn() as c:
        n = c.executemany("""
            INSERT OR REPLACE INTO cot_history
            (instrument, report_date, net_position, net_change, oi, oi_change, long_all, short_all, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows).rowcount
    return len(rows)


def get_cot_history(instrument: str, weeks: int = 156) -> Optional[pd.DataFrame]:
    """
    Odczyt z archiwum: ostatnie 'weeks' tygodni (26 = 6 mies., 52 = 1 rok, 156 = 3 lata).
    Zwraca DataFrame z kolumnami: date, net_position, net_change, oi, oi_change (posortowane po dacie rosnąco).
    """
    init_archive()
    with _conn() as c:
        rows = c.execute("""
            SELECT report_date, net_position, net_change, oi, oi_change
            FROM cot_history WHERE instrument = ?
            ORDER BY report_date DESC LIMIT ?
        """, (instrument.upper(), weeks)).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["report_date", "net_position", "net_change", "oi", "oi_change"])
    df["date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["net_change"] = df["net_position"].diff()
    return df
