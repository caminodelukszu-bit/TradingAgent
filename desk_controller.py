# =============================================================================
# desk_controller.py - Pełny desk: łączenie research → decyzja → execution
# Na podstawie instrukcji (top_ideas) i limitów risk generuje sugestie zleceń
# i opcjonalnie wykonuje je w trybie paper (lub tylko raportuje).
# =============================================================================

from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from config import DESK_MODE, MAX_POSITIONS_TOTAL
except ImportError:
    DESK_MODE = "paper"
    MAX_POSITIONS_TOTAL = 5


def get_suggested_orders(
    instruction: Dict[str, Any],
    risk: Dict[str, Any],
    max_orders: int = 3,
) -> List[Dict[str, Any]]:
    """
    Z instrukcji (top_ideas) i risk zwraca listę sugerowanych zleceń.
    Nie składa zleceń – tylko zwraca do wyświetlenia lub przekazania do execution.
    """
    if instruction.get("decision") == "NIE WCHODŹ":
        return []
    try:
        from position_tracker import get_open_positions
        current_count = len(get_open_positions())
    except Exception:
        current_count = 0
    top_ideas = instruction.get("top_ideas") or []
    max_pozycje = risk.get("max_pozycje", MAX_POSITIONS_TOTAL)
    # Nie sugeruj więcej niż wolne sloty (max_pozycje - current) i nie więcej niż max_orders
    limit = min(max_orders, max(0, max_pozycje - current_count))
    suggested = []
    for i, idea in enumerate(top_ideas[:limit]):
        co = idea.get("co", "")
        if not co:
            continue
        # "EUR/USD LONG" -> symbol EURUSD, side LONG
        parts = co.strip().split()
        if len(parts) >= 2:
            symbol_raw = parts[0].replace("/", "")
            side = parts[1].upper()
        else:
            symbol_raw = co.replace("/", "").replace(" ", "")[:10]
            side = "LONG"
        symbol = symbol_raw.upper()
        pct = idea.get("suggested_pct") or 0.5
        rationale = idea.get("rationale", "")
        suggested.append({
            "symbol": symbol,
            "side": side,
            "size_pct": pct,
            "rationale": rationale,
            "co": co,
        })
    return suggested


def execute_suggested_orders(
    suggested: List[Dict[str, Any]],
    dry_run: bool = True,
) -> List[Dict[str, Any]]:
    """
    Wykonuje listę sugerowanych zleceń (przez execution_engine).
    dry_run=True: tylko zwraca co by złożono, bez wywołania place_order.
    dry_run=False: wywołuje place_order (w paper zapisze do desk.db).
    """
    from execution_engine import place_order, DESK_MODE
    results = []
    for s in suggested:
        if dry_run:
            results.append({"ok": True, "dry_run": True, "message": f"[DRY-RUN] {s['side']} {s['symbol']} {s['size_pct']}%", "order_id": None})
            continue
        if DESK_MODE == "live":
            # W live bez auto – tylko log
            results.append({"ok": True, "live_skip": True, "message": f"[LIVE – wykonaj ręcznie] {s['side']} {s['symbol']} {s['size_pct']}%", "order_id": None})
            continue
        r = place_order(
            symbol=s["symbol"],
            side=s["side"],
            size_pct=s["size_pct"],
            rationale=s.get("rationale", ""),
            source="desk_controller",
        )
        results.append({**r, "symbol": s["symbol"], "side": s["side"], "size_pct": s["size_pct"]})
    return results


def run_desk_cycle(
    instruction: Dict[str, Any],
    risk: Dict[str, Any],
    execute: bool = False,
    max_orders: int = 3,
) -> Dict[str, Any]:
    """
    Jeden cykl desk: sugestie zleceń + opcjonalnie wykonanie.
    execute=False: tylko suggested_orders (do raportu).
    execute=True: wywołuje execute_suggested_orders(dry_run=False) w trybie paper.
    """
    suggested = get_suggested_orders(instruction, risk, max_orders=max_orders)
    executed = []
    if suggested and execute:
        executed = execute_suggested_orders(suggested, dry_run=False)
    return {
        "decision": instruction.get("decision"),
        "suggested_orders": suggested,
        "executed": executed,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
