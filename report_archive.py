# =============================================================================
# report_archive.py - Archiwum raportow (SQLite): zapis, lista, porownanie z poprzednim
# =============================================================================

import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_SCRIPT_DIR, "data", "report_archive.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                report_time TEXT NOT NULL,
                decision TEXT,
                summary TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(report_date DESC, report_time DESC)")


def save_report(
    report_date: str,
    report_time: str,
    decision: str = "",
    summary: Optional[Dict[str, Any]] = None,
) -> int:
    """Zapisuje raport do archiwum. Zwraca id wstawionego rekordu."""
    _init_db()
    created = datetime.now().isoformat()
    summary_json = json.dumps(summary, ensure_ascii=False) if summary else "{}"
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO reports (report_date, report_time, decision, summary, created_at) VALUES (?, ?, ?, ?, ?)",
            (report_date, report_time, decision, summary_json, created),
        )
        return cur.lastrowid


def list_reports(limit: int = 200) -> List[Dict[str, Any]]:
    """Lista raportow od najnowszych. Kazdy element: id, report_date, report_time, decision, summary (dict), created_at."""
    _init_db()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, report_date, report_time, decision, summary, created_at FROM reports ORDER BY report_date DESC, report_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["summary"] = json.loads(d["summary"] or "{}")
        except Exception:
            d["summary"] = {}
        out.append(d)
    return out


def get_reports_for_quarter(limit: int = 123) -> List[Dict[str, Any]]:
    """
    Ostatnie N raportow do analizy kwartalnej (~1 kwartal przy 4 raporty/dzien).
    Bez dyskusji – wszystkie podlegaja analizie przed wydaniem biezacego raportu.
    """
    return list_reports(limit=limit)


def get_report(report_id: int) -> Optional[Dict[str, Any]]:
    """Pobiera pojedynczy raport po id."""
    _init_db()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, report_date, report_time, decision, summary, created_at FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["summary"] = json.loads(d["summary"] or "{}")
    except Exception:
        d["summary"] = {}
    return d


def get_two_for_comparison(report_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Zwraca (raport_biezacy, raport_poprzedni) dla porownania ciaglosci.
    raport_poprzedni to raport o id < report_id (najblizszy w czasie wstecz).
    """
    current = get_report(report_id)
    if not current:
        return None, None
    _init_db()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, report_date, report_time, decision, summary, created_at FROM reports WHERE id < ? ORDER BY id DESC LIMIT 1",
            (report_id,),
        ).fetchone()
    prev = None
    if row:
        prev = dict(row)
        try:
            prev["summary"] = json.loads(prev["summary"] or "{}")
        except Exception:
            prev["summary"] = {}
    return current, prev


def diff_reports(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Zwraca zestawienie roznic miedzy dwoma raportami (ciaglosc / zmiany).
    Klucze: decision_changed, signals_added, signals_removed, signals_changed, macro_changed, summary_text.
    """
    out = {
        "decision_changed": False,
        "decision_prev": "",
        "decision_curr": "",
        "signals_added": [],
        "signals_removed": [],
        "signals_changed": [],
        "macro_changed": {},
        "summary_text": [],
    }
    curr_s = (current.get("summary") or {})
    prev_s = (previous.get("summary") or {})

    out["decision_curr"] = current.get("decision") or ""
    out["decision_prev"] = previous.get("decision") or ""
    out["decision_changed"] = out["decision_curr"] != out["decision_prev"]
    if out["decision_changed"]:
        out["summary_text"].append(f"Zmiana decyzji: {out['decision_prev']} → {out['decision_curr']}")

    curr_sigs = {s.get("instrument"): s for s in curr_s.get("signals", []) if s.get("instrument")}
    prev_sigs = {s.get("instrument"): s for s in prev_s.get("signals", []) if s.get("instrument")}
    for k in curr_sigs:
        if k not in prev_sigs:
            out["signals_added"].append(k)
        else:
            c, p = curr_sigs[k], prev_sigs[k]
            if c.get("bias") != p.get("bias") or c.get("score") != p.get("score") or c.get("conviction") != p.get("conviction"):
                out["signals_changed"].append({"instrument": k, "prev": p, "curr": c})
    for k in prev_sigs:
        if k not in curr_sigs:
            out["signals_removed"].append(k)
    if out["signals_added"]:
        out["summary_text"].append("Nowe sygnaly: " + ", ".join(out["signals_added"]))
    if out["signals_removed"]:
        out["summary_text"].append("Usuniete sygnaly: " + ", ".join(out["signals_removed"]))
    if out["signals_changed"]:
        out["summary_text"].append("Zmienione sygnaly: " + ", ".join({x["instrument"] for x in out["signals_changed"]}))

    curr_m = curr_s.get("macro") or {}
    prev_m = prev_s.get("macro") or {}
    for key in set(curr_m) | set(prev_m):
        cv, pv = curr_m.get(key), prev_m.get(key)
        if cv != pv and (cv is not None or pv is not None):
            out["macro_changed"][key] = {"prev": pv, "curr": cv}
    if out["macro_changed"]:
        out["summary_text"].append("Zmiana makro: " + ", ".join(out["macro_changed"].keys()))

    return out
