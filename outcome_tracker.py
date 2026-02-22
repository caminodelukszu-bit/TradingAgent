# =============================================================================
# outcome_tracker.py - SofikaMax Agent
# Zapis sygnalow i weryfikacja: ktore sie sprawdzily (uczenie na historii).
# =============================================================================

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

OUTCOMES_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outcomes.db")

# Para (display) -> symbol yfinance (close price)
YF_SYMBOLS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "AUD/USD": "AUDUSD=X",
    "USD/JPY": "USDJPY=X", "USD/CHF": "USDCHF=X", "USD/CAD": "USDCAD=X",
    "XAU/USD": "GC=F", "XAG/USD": "SI=F", "BTC/USD (USDT)": "BTC-USD",
}


def _conn():
    return sqlite3.connect(OUTCOMES_DB)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                para TEXT NOT NULL,
                kierunek TEXT NOT NULL,
                score_inst INTEGER,
                conviction TEXT,
                sila INTEGER,
                situation_type TEXT,
                event_risk_level TEXT,
                event_high_count INTEGER,
                upcoming_events_summary TEXT,
                regime_type TEXT,
                above_ema INTEGER,
                primary_driver TEXT,
                rationale TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                horizon_days INTEGER DEFAULT 14,
                checked_at TEXT NOT NULL,
                price_start REAL,
                price_end REAL,
                pct_change REAL,
                hit INTEGER NOT NULL,
                note TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sig_date ON signals(report_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_out_sig ON outcomes(signal_id)")
        # Najpierw dodaj kolumne horizon_days jesli stara baza jej nie miala (przed indeksem!)
        try:
            c.execute("ALTER TABLE outcomes ADD COLUMN horizon_days INTEGER DEFAULT 14")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_out_horizon ON outcomes(signal_id, horizon_days)")
        except sqlite3.OperationalError:
            pass
        for col, typ in [
            ("event_risk_level", "TEXT"), ("event_high_count", "INTEGER"),
            ("upcoming_events_summary", "TEXT"), ("regime_type", "TEXT"), ("above_ema", "INTEGER"),
            ("primary_driver", "TEXT"), ("rationale", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE signals ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass


def _para_to_instrument(para: str) -> str:
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}
    if para in nazwa_do_inst:
        return nazwa_do_inst[para]
    return para.split("/")[0] if "/" in para else para


def save_signals(
    report_date: str,
    pary_usd: List[Dict],
    top_n: int = 5,
    signal_context: Optional[Dict[str, Dict[str, Any]]] = None,
) -> int:
    """
    Zapisuje top N sygnalow z pary_usd (vs USD).
    signal_context: dict[instrument] = {..., primary_driver, rationale}.
    """
    init_db()
    to_save = sorted(pary_usd, key=lambda x: x.get("sila_sygnalu", 0), reverse=True)[:top_n]
    if not to_save:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ctx = signal_context or {}
    with _conn() as c:
        for p in to_save:
            inst = _para_to_instrument(p.get("para", ""))
            c_ = ctx.get(inst, {})
            c.execute("""
                INSERT INTO signals (
                    report_date, para, kierunek, score_inst, conviction, sila, situation_type,
                    event_risk_level, event_high_count, upcoming_events_summary, regime_type, above_ema,
                    primary_driver, rationale, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_date,
                p.get("para", ""),
                p.get("kierunek", ""),
                p.get("score_inst", 0),
                p.get("conviction", ""),
                p.get("sila_sygnalu", 0),
                p.get("situation_type", ""),
                c_.get("event_risk_level"),
                c_.get("event_high_count"),
                c_.get("upcoming_events_summary"),
                c_.get("regime_type"),
                1 if c_.get("above_ema") else 0,
                c_.get("primary_driver"),
                c_.get("rationale"),
                now,
            ))
    return len(to_save)


def _fetch_price(symbol: str, d: datetime) -> Optional[float]:
    try:
        import yfinance as yf
        end = d + timedelta(days=5)
        df = yf.download(symbol, start=d - timedelta(days=5), end=end, progress=False, auto_adjust=True, timeout=10)
        if df is None or df.empty:
            return None
        close = df["Close"] if "Close" in df.columns else (df.Close if hasattr(df, "Close") else None)
        if close is None:
            return None
        # Pierwsza notowanie w lub po dacie d
        mask = df.index >= d
        if not mask.any():
            return float(close.iloc[-1])
        return float(close.loc[mask].iloc[0])
    except Exception:
        return None


HORIZONS_DAYS = [7, 14, 21]


def update_outcomes(days_ago: int = 21, max_to_check: int = 25) -> int:
    """Dla kazdego horyzontu (7/14/21d) dopisuje brakujace outcomes. Zwraca l. zaktualizowanych."""
    init_db()
    today = datetime.now().date()
    updated = 0
    for horizon in HORIZONS_DAYS:
        cutoff = (today - timedelta(days=horizon)).strftime("%Y-%m-%d")
        with _conn() as c:
            rows = c.execute("""
                SELECT s.id, s.report_date, s.para, s.kierunek
                FROM signals s
                WHERE s.report_date <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM outcomes o WHERE o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
                )
                ORDER BY s.report_date DESC
                LIMIT ?
            """, (cutoff, horizon, max_to_check)).fetchall()
        for row in rows:
            sig_id, report_date, para, kierunek = row
            symbol = YF_SYMBOLS.get(para)
            if not symbol:
                continue
            try:
                d0 = datetime.strptime(report_date, "%Y-%m-%d")
                d1 = d0 + timedelta(days=horizon)
                p0 = _fetch_price(symbol, d0)
                p1 = _fetch_price(symbol, d1)
                if p0 is None or p1 is None or p0 == 0:
                    continue
                pct = (p1 - p0) / p0 * 100
                if kierunek == "SHORT":
                    pct = -pct
                hit = 1 if pct > 0 else 0
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                with _conn() as c2:
                    c2.execute("""
                        INSERT INTO outcomes (signal_id, horizon_days, checked_at, price_start, price_end, pct_change, hit, note)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sig_id, horizon, now, p0, p1, round(pct, 2), hit, None))
                updated += 1
            except Exception:
                continue
    return updated


def get_verified(limit: int = 10, horizon_days: int = 14) -> List[Dict[str, Any]]:
    """Zwraca liste sygnalow z wynikami weryfikacji (domyslnie horyzont 14d)."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT s.report_date, s.para, s.kierunek, s.score_inst, s.conviction,
                   o.pct_change, o.hit, o.checked_at, COALESCE(o.horizon_days, 14)
            FROM signals s
            INNER JOIN outcomes o ON o.signal_id = s.id
            WHERE COALESCE(o.horizon_days, 14) = ?
            ORDER BY o.checked_at DESC
            LIMIT ?
        """, (horizon_days, limit)).fetchall()
    return [
        {
            "report_date": r[0],
            "para": r[1],
            "kierunek": r[2],
            "score_inst": r[3],
            "conviction": r[4],
            "pct_change": r[5],
            "hit": bool(r[6]),
            "checked_at": r[7],
            "horizon_days": r[8],
        }
        for r in rows
    ]


def get_aggregated_feedback(min_samples: int = 2, horizon_days: int = 14) -> List[Dict[str, Any]]:
    """Agregacja wyników wg typu sytuacji. Domyślnie horyzont 14d."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT COALESCE(s.situation_type, 'OTHER') AS stype,
                   COUNT(*) AS total, SUM(o.hit) AS hits
            FROM signals s
            INNER JOIN outcomes o ON o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
            GROUP BY COALESCE(s.situation_type, 'OTHER')
            HAVING COUNT(*) >= ?
        """, (horizon_days, min_samples)).fetchall()
    return [
        {
            "situation_type": r[0] or "OTHER",
            "total": r[1],
            "hits": r[2],
            "hit_rate_pct": round(100 * r[2] / r[1], 1) if r[1] else 0,
        }
        for r in rows
    ]


def get_conviction_aggregation(min_samples: int = 1, horizon_days: int = 14) -> List[Dict[str, Any]]:
    """Agregacja trafności wg poziomu conviction (WYSOKI / UMIARKOWANY / NISKI). Do kalibracji."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT COALESCE(s.conviction, 'PASS') AS conv,
                   COUNT(*) AS total, SUM(o.hit) AS hits
            FROM signals s
            INNER JOIN outcomes o ON o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
            WHERE s.conviction IS NOT NULL AND s.conviction != ''
            GROUP BY s.conviction
            HAVING COUNT(*) >= ?
        """, (horizon_days, min_samples)).fetchall()
    return [
        {
            "conviction": r[0],
            "total": r[1],
            "hits": r[2],
            "hit_rate_pct": round(100 * r[2] / r[1], 1) if r[1] else 0,
        }
        for r in rows
    ]


def get_event_risk_aggregation(min_samples: int = 1, horizon_days: int = 14) -> List[Dict[str, Any]]:
    """Agregacja trafności wg event_risk_level (NISKI / WYSOKI / KRYTYCZNY). Do analizy event vs trafność."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT COALESCE(s.event_risk_level, 'NISKI') AS lvl,
                   COUNT(*) AS total, SUM(o.hit) AS hits
            FROM signals s
            INNER JOIN outcomes o ON o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
            GROUP BY COALESCE(s.event_risk_level, 'NISKI')
            HAVING COUNT(*) >= ?
        """, (horizon_days, min_samples)).fetchall()
    return [
        {
            "event_risk_level": r[0],
            "total": r[1],
            "hits": r[2],
            "hit_rate_pct": round(100 * r[2] / r[1], 1) if r[1] else 0,
        }
        for r in rows
    ]


def get_similar_signals(
    situation_id: str,
    regime_type: str = None,
    limit: int = 5,
    horizon_days: int = 14,
) -> List[Dict[str, Any]]:
    """Ostatnie N sygnałów z tym samym situation_id (i opcjonalnie regime). Zwraca z outcome (analogi)."""
    init_db()
    if regime_type:
        with _conn() as c:
            rows = c.execute("""
                SELECT s.report_date, s.para, s.kierunek, o.hit, o.pct_change
                FROM signals s
                INNER JOIN outcomes o ON o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
                WHERE COALESCE(s.situation_type, 'OTHER') = ? AND (s.regime_type = ? OR s.regime_type IS NULL)
                ORDER BY s.report_date DESC
                LIMIT ?
            """, (horizon_days, situation_id, regime_type or "", limit)).fetchall()
    else:
        with _conn() as c:
            rows = c.execute("""
                SELECT s.report_date, s.para, s.kierunek, o.hit, o.pct_change
                FROM signals s
                INNER JOIN outcomes o ON o.signal_id = s.id AND COALESCE(o.horizon_days, 14) = ?
                WHERE COALESCE(s.situation_type, 'OTHER') = ?
                ORDER BY s.report_date DESC
                LIMIT ?
            """, (horizon_days, situation_id, limit)).fetchall()
    return [
        {"report_date": r[0], "para": r[1], "kierunek": r[2], "hit": bool(r[3]), "pct_change": r[4]}
        for r in rows
    ]


def get_verified_by_horizon(horizon_days: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Weryfikacje dla danego horyzontu (7/14/21d) – do sekcji wiele horyzontów."""
    return get_verified(limit=limit, horizon_days=horizon_days)


# =============================================================================
# FEEDBACK UŻYTKOWNIKA (przydatne / nie)
# =============================================================================

def init_user_feedback_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                para TEXT NOT NULL,
                useful INTEGER NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_uf_date ON user_feedback(report_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_uf_para ON user_feedback(para)")


def save_user_feedback(report_date: str, para: str, useful: bool, note: str = None) -> int:
    """Zapisuje ocenę użytkownika: useful=True (przydatne) / False (nie). Zwraca id."""
    init_db()
    init_user_feedback_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        c.execute("""
            INSERT INTO user_feedback (report_date, para, useful, note, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (report_date, para, 1 if useful else 0, note or "", now))
        return c.lastrowid or 0


def get_user_feedback_aggregation() -> List[Dict[str, Any]]:
    """Agregacja: które pary/instrumenty użytkownik najczęściej ocenił pozytywnie (do priorytetyzacji)."""
    init_user_feedback_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT para, COUNT(*) AS total, SUM(useful) AS useful_count
            FROM user_feedback
            GROUP BY para
            HAVING COUNT(*) >= 1
            ORDER BY SUM(useful) DESC, COUNT(*) DESC
        """).fetchall()
    return [
        {"para": r[0], "total": r[1], "useful_count": r[2], "useful_pct": round(100 * r[2] / r[1], 0) if r[1] else 0}
        for r in rows
    ]


if __name__ == "__main__":
    init_db()
    print("Ostatnie weryfikacje:", get_verified(5))
