# =============================================================================
# position_tracker.py - Pelny desk: ksiega pozycji (otwarte / zamkniete)
# Uzywa desk.db z execution_engine. Ekspozycja per symbol dla risk.
# =============================================================================

from typing import List, Dict, Any

try:
    from execution_engine import get_positions, close_position, init_desk_db
except ImportError:
    def get_positions(open_only=True):
        return []
    def close_position(position_id, reason="manual"):
        return {"ok": False, "message": "Brak execution_engine"}
    def init_desk_db():
        pass


def get_open_positions() -> List[Dict[str, Any]]:
    """Otwarte pozycje (z paper lub brokera)."""
    return get_positions(open_only=True)


def get_exposure_by_symbol() -> Dict[str, Dict[str, Any]]:
    """Ekspozycja per symbol dla risk_engine. Zwraca dict symbol -> side, count, size_pct."""
    positions = get_open_positions()
    out = {}
    for p in positions:
        sym = (p.get("symbol") or "").upper()
        if not sym:
            continue
        side = p.get("side", "LONG")
        if sym not in out:
            out[sym] = {"side": side, "size_pct": 0.0, "count": 0}
        out[sym]["count"] += 1
        out[sym]["size_pct"] = out[sym].get("size_pct", 0) + 0.5
    return out


def get_positions_summary() -> Dict[str, Any]:
    """Podsumowanie: liczba otwartych, lista symboli."""
    open_ = get_open_positions()
    symbols = list(dict.fromkeys([p.get("symbol") for p in open_ if p.get("symbol")]))
    return {"count": len(open_), "symbols": symbols, "positions": open_}
