# =============================================================================
# execution_engine.py - Pełny desk: warstwa wykonania zleceń
# Interfejs: place_order, get_positions, get_account.
# Adaptery: paper (symulacja), w przyszłości MT5/OANDA/IB.
# =============================================================================

from typing import List, Dict, Any, Optional
from datetime import datetime
import os

try:
    from config import DESK_MODE, BROKER_ADAPTER
except ImportError:
    DESK_MODE = "paper"   # paper | live (live = tylko sugestie, bez auto)
    BROKER_ADAPTER = "paper"

# Baza pozycji i zleceń (wspólna z position_tracker)
DESK_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desk.db")


def _conn():
    import sqlite3
    return sqlite3.connect(DESK_DB)


def init_desk_db():
    """Tabele: orders (audit zleceń), positions (otwarte pozycje)."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size_units REAL,
                size_pct REAL,
                rationale TEXT,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size_units REAL NOT NULL,
                entry_price REAL,
                entry_time TEXT NOT NULL,
                source TEXT NOT NULL,
                rationale TEXT,
                closed_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_pos_symbol ON positions(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pos_closed ON positions(closed_at)")


# --- Interfejs broker adaptera ---

def place_order(
    symbol: str,
    side: str,
    size_pct: float,
    rationale: str = "",
    source: str = "desk",
) -> Dict[str, Any]:
    """
    Składa zlecenie (lub symuluje w trybie paper).
    symbol: np. EURUSD, XAUUSD
    side: LONG | SHORT
    size_pct: procent kapitału (0.25–1.5)
    Zwraca: {"ok": bool, "order_id": int|None, "message": str, "filled": bool}
    """
    init_desk_db()
    if BROKER_ADAPTER == "paper":
        return _paper_place_order(symbol, side, size_pct, rationale, source)
    # Tu w przyszłości: elif BROKER_ADAPTER == "mt5": return _mt5_place_order(...)
    return {"ok": False, "order_id": None, "message": f"Nieznany adapter: {BROKER_ADAPTER}", "filled": False}


def _paper_place_order(symbol: str, side: str, size_pct: float, rationale: str, source: str) -> Dict[str, Any]:
    """Symulacja: zapis do orders + positions (bez realnego zlecenia)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        c.execute("""
            INSERT INTO orders (symbol, side, size_units, size_pct, rationale, source, status, created_at)
            VALUES (?, ?, 0, ?, ?, ?, 'FILLED', ?)
        """, (symbol, side, size_pct, rationale, source, now))
        order_id = c.lastrowid
        c.execute("""
            INSERT INTO positions (order_id, symbol, side, size_units, entry_price, entry_time, source, rationale)
            VALUES (?, ?, ?, 0, 0, ?, 'paper', ?)
        """, (order_id, symbol, side, now, rationale))
    return {"ok": True, "order_id": order_id, "message": f"[PAPER] {side} {symbol} {size_pct}%", "filled": True}


def get_positions(open_only: bool = True) -> List[Dict[str, Any]]:
    """Zwraca listę pozycji (z bazy desk lub z brokera). open_only=True = tylko otwarte."""
    init_desk_db()
    if BROKER_ADAPTER == "paper":
        return _paper_get_positions(open_only)
    return []


def _paper_get_positions(open_only: bool) -> List[Dict[str, Any]]:
    with _conn() as c:
        if open_only:
            rows = c.execute("""
                SELECT id, symbol, side, size_units, entry_price, entry_time, source, rationale
                FROM positions WHERE closed_at IS NULL ORDER BY entry_time DESC
            """).fetchall()
        else:
            rows = c.execute("""
                SELECT id, symbol, side, size_units, entry_price, entry_time, source, rationale, closed_at
                FROM positions ORDER BY entry_time DESC
            """).fetchall()
    return [
        {
            "id": r[0], "symbol": r[1], "side": r[2], "size_units": r[3],
            "entry_price": r[4], "entry_time": r[5], "source": r[6], "rationale": r[7],
            "closed_at": r[8] if len(r) > 8 else None,
        }
        for r in rows
    ]


def close_position(position_id: int, reason: str = "manual") -> Dict[str, Any]:
    """Zamyka pozycję (w paper: ustawia closed_at)."""
    init_desk_db()
    with _conn() as c:
        c.execute("UPDATE positions SET closed_at = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), position_id))
    return {"ok": True, "message": f"Pozycja {position_id} zamknięta ({reason})."}


def get_account() -> Dict[str, Any]:
    """Saldo / equity (paper: z config lub 0; live: z brokera)."""
    try:
        from config import PAPER_CAPITAL
    except ImportError:
        PAPER_CAPITAL = 0.0
    if BROKER_ADAPTER == "paper":
        return {"balance": PAPER_CAPITAL, "equity": PAPER_CAPITAL, "source": "paper"}
    return {"balance": 0, "equity": 0, "source": "unknown"}
