# =============================================================================
# feedback_analyzer.py - SofikaMax Agent
# Analiza feedbacku (ML): co działa, co nie działa, co łączyć, co wyeliminować.
# Automatyczne wnioski z weryfikacji sygnałów wg typu sytuacji.
# =============================================================================

from typing import List, Dict, Any


def apply_learned_conviction(
    conviction: str,
    situation_id: str,
    situation_types_low: List[str],
) -> str:
    """
    Obniża conviction o jeden poziom, gdy typ sytuacji ma niską trafność historyczną.
    WYSOKI -> UMIARKOWANY, UMIARKOWANY -> NISKI, NISKI/PASS bez zmiany.
    """
    if not situation_types_low or situation_id not in situation_types_low:
        return conviction
    if conviction == "WYSOKI":
        return "UMIARKOWANY"
    if conviction == "UMIARKOWANY":
        return "NISKI"
    return conviction

PROG_DZIALA = 55.0   # hit rate >= 55% -> "działa"
PROG_NIE_DZIALA = 45.0  # hit rate <= 45% -> "nie działa"

# Jakość sytuacji na podstawie trafności (używane w workflow i learned conviction)
QUALITY_GOOD = 1.0
QUALITY_NEUTRAL = 0.5
QUALITY_BAD = 0.0


def get_situation_quality_map(aggregated: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Zwraca mapę: typ_sytuacji -> jakość (1.0 = działa, 0.5 = neutral, 0.0 = nie działa).
    Używane do sortowania workflow i learned conviction.
    """
    out = {}
    for row in aggregated:
        stype = row.get("situation_type", "OTHER")
        rate = row.get("hit_rate_pct", 0)
        if rate >= PROG_DZIALA:
            out[stype] = QUALITY_GOOD
        elif rate <= PROG_NIE_DZIALA:
            out[stype] = QUALITY_BAD
        else:
            out[stype] = QUALITY_NEUTRAL
    return out


def analyze_feedback(aggregated: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Na podstawie agregacji wyników (outcome_tracker.get_aggregated_feedback())
    zwraca: co_dziala, co_nie_dziala, rekomendacja_workflow, tabela.
    """
    co_dziala = []
    co_nie_dziala = []
    neutralne = []
    for row in aggregated:
        stype = row.get("situation_type", "OTHER")
        rate = row.get("hit_rate_pct", 0)
        total = row.get("total", 0)
        label = _label_sytuacji(stype)
        entry = f"{label}: {rate}% trafionych (n={total})"
        if rate >= PROG_DZIALA:
            co_dziala.append(entry)
        elif rate <= PROG_NIE_DZIALA:
            co_nie_dziala.append(entry)
        else:
            neutralne.append(entry)

    # Rekomendacja workflow: łączyć to co działa, unikać / ograniczać to co nie
    rekomendacja = []
    if co_dziala:
        rekomendacja.append("Priorytet: sytuacje z wysoką trafnością – kontynuuj obecny workflow.")
    if co_nie_dziala:
        rekomendacja.append("Ogranicz ekspozycję w sytuacjach o niskiej trafności lub czekaj na lepsze potwierdzenie.")
    if neutralne and not co_dziala:
        rekomendacja.append("Niewystarczająca przewaga w danych – koncentruj się na wysokiej conviction i dywersyfikacji.")
    if not rekomendacja:
        rekomendacja.append("Zbieraj dalej dane weryfikacyjne; przy min. 2–3 sytuacjach z historią wnioski będą pewniejsze.")

    situation_quality_map = get_situation_quality_map(aggregated)
    situation_types_low = [st for st, q in situation_quality_map.items() if q == QUALITY_BAD]

    return {
        "co_dziala":             co_dziala,
        "co_nie_dziala":         co_nie_dziala,
        "neutralne":             neutralne,
        "rekomendacja":          rekomendacja,
        "tabela":                aggregated,
        "situation_quality_map": situation_quality_map,
        "situation_types_low":   situation_types_low,
    }


def _label_sytuacji(situation_type: str) -> str:
    labels = {
        "TREND_CORRECTION": "Korekta w trendzie (COT)",
        "RANGE_RV":         "Range / mean reversion",
        "LATE_CYCLE_RV":    "Późna faza cyklu",
        "EVENT":            "Wydarzenie makro",
        "OTHER":            "Inne",
    }
    return labels.get(situation_type, situation_type)
