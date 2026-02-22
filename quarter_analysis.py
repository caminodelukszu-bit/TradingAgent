# =============================================================================
# quarter_analysis.py - Analiza ostatnich N raportów (np. 123 = ~1 kwartał przy 4/dzień)
# Wykonywana przed wydaniem bieżącego raportu; wynik wykorzystywany w narracji ciągłości (bez opisywania każdego raportu).
# =============================================================================

from typing import List, Dict, Any
from collections import Counter


# ~31 dni × 4 raporty/dzień ≈ 124; 123 = ostatni pełny kwartał pod kontrolą
# Nadpisywane z config.QUARTER_REPORTS_LIMIT jeśli dostępne
try:
    from config import QUARTER_REPORTS_LIMIT
except ImportError:
    QUARTER_REPORTS_LIMIT = 123


def _norm_decision(decision: str) -> str:
    if not decision:
        return "inne"
    d = decision.upper()
    if "NIE WCHODŹ" in d:
        return "CZEKAJ"
    if "OGRANICZENIAMI" in d:
        return "ostrożne wejście"
    if "WCHODŹ" in d or "MOŻESZ" in d:
        return "wejście"
    return "inne"


def analyze_quarter_reports(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analizuje listę raportów (od najnowszych). Nie opisuje każdego – agreguje:
    rozkład decyzji, najczęstsze instrumenty w rekomendacjach, trend makro, ewentualne serie (np. 3. tydzień CZEKAJ).
    Zwraca dict: decision_distribution, top_instruments, macro_trend_summary, streak_czekaj, summary_paragraph_pl, n_reports.
    """
    out = {
        "n_reports": len(reports),
        "decision_distribution": {},
        "top_instruments": [],
        "macro_trend_summary": "",
        "streak_czekaj": 0,
        "summary_paragraph_pl": "",
    }
    if not reports:
        out["summary_paragraph_pl"] = "Brak archiwum raportów – analiza kwartalna będzie dostępna po zebraniu danych."
        return out

    # Rozkład decyzji
    decisions = [_norm_decision(r.get("decision", "")) for r in reports]
    out["decision_distribution"] = dict(Counter(decisions))

    # Serie CZEKAJ od początku listy (najnowsze)
    for r in reports:
        if _norm_decision(r.get("decision", "")) == "CZEKAJ":
            out["streak_czekaj"] += 1
        else:
            break

    # Najczęstsze instrumenty w sygnałach (top 3–5)
    inst_count: Counter = Counter()
    for r in reports:
        summary = r.get("summary") or {}
        for s in summary.get("signals", [])[:5]:
            inst = s.get("instrument")
            if inst:
                inst_count[inst] += 1
    out["top_instruments"] = [x[0] for x in inst_count.most_common(5)]

    # Trend makro (DXY, FED) – czy rośnie/maleje w czasie (reports są od najnowszych, więc indeks 0 = ostatni)
    dxy_vals = []
    fed_vals = []
    for r in reports[:min(30, len(reports))]:  # ostatnie ~30 raportów
        summary = r.get("summary") or {}
        macro = summary.get("macro") or {}
        if macro.get("DXY") is not None:
            try:
                dxy_vals.append(float(macro["DXY"]))
            except (TypeError, ValueError):
                pass
        if macro.get("FED") is not None:
            try:
                fed_vals.append(float(macro["FED"]))
            except (TypeError, ValueError):
                pass
    if len(dxy_vals) >= 2:
        dxy_first, dxy_last = dxy_vals[-1], dxy_vals[0]
        out["macro_trend_summary"] = f"DXY w okresie: {dxy_first:.1f} → {dxy_last:.1f} (wzrost)" if dxy_last > dxy_first else f"DXY w okresie: {dxy_first:.1f} → {dxy_last:.1f} (spadek)"
    if len(fed_vals) >= 2:
        fed_first, fed_last = fed_vals[-1], fed_vals[0]
        frag = f" Stopy FED: {fed_first:.2f}% → {fed_last:.2f}%."
        out["macro_trend_summary"] = (out["macro_trend_summary"] or "").strip() + frag

    # Jedno zdanie / krótki akapit po polsku do raportu
    n = out["n_reports"]
    dec = out["decision_distribution"]
    czekaj_pct = round(100 * dec.get("CZEKAJ", 0) / n) if n else 0
    wejscie_pct = round(100 * (dec.get("wejście", 0) + dec.get("ostrożne wejście", 0)) / n) if n else 0
    top_inst = ", ".join(out["top_instruments"][:3]) if out["top_instruments"] else "–"
    streak = out["streak_czekaj"]
    macro_t = (out["macro_trend_summary"] or "").strip()

    parts = [
        f"W ostatnim kwartale przeanalizowano {n} raportów (ok. 4 dziennie). "
        f"Decyzja CZEKAJ w {czekaj_pct}% raportów, wejście (łącznie z ostrożnym) w {wejscie_pct}%. "
    ]
    if top_inst != "–":
        parts.append(f"Najczęstsze rekomendacje: {top_inst}. ")
    if streak >= 2:
        parts.append(f"Obecnie seria {streak} raportów z rekomendacją CZEKAJ z rzędu – ryzyko lub jakość setupów w ostatnich dniach nie uzasadniała wejścia. ")
    if macro_t:
        parts.append(f"Makro (DXY/FED): {macro_t}")
    out["summary_paragraph_pl"] = "".join(parts).strip()

    return out
