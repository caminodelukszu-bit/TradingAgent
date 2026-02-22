# =============================================================================
# situation_engine.py - SofikaMax Agent
# Zmienne z wielu modułów łączą się w jedną zdefiniowaną SITUACJĘ.
# Sytuacja jest podstawą pod 3 META TAGI i 2 warianty analizy.
# =============================================================================

from typing import Dict, Any, List

# Wszystkie zmienne wejściowe używane do definicji sytuacji (kompleksowa analiza)
ZMIENNE_OPIS = [
    "cot_momentum",      # COT: BULLISH / BEARISH / MIXED
    "cot_zscore",        # COT: siła pozycji (Z-score)
    "cykl_faza",         # Cykl: RECOVERY / EXPANSION / SLOWDOWN / CONTRACTION
    "cykl_zegar",        # Zegar: GOLDILOCKS / REFLATION / DEFLATION / STAGFLATION
    "cykl_dojrzalosc",   # EARLY / MID / LATE
    "surprise_4w",       # Zaskoczenia makro (trend 4w)
    "event_high_count",  # Liczba wydarzeń wysokiej wagi
    "event_risk_level",  # NISKI / WYSOKI / KRYTYCZNY
    "regime_typ",        # TRENDING BULLISH / RANGE / TRENDING BEARISH
    "regime_range",      # Czy RANGE (kara)
    "flow_rezim",        # RISK-ON / RISK-OFF / NEUTRALNY
    "flow_score",        # Flow score 0-20
    "flow_dywergencja",  # Dywergencja COT-flow
    "scoring_conviction",# WYSOKI / UMIARKOWANY / NISKI / PASS
    "scoring_bias",      # KUP / SPRZEDAJ / CZEKAJ
]


def definiuj_sytuacje(
    cot: Dict,
    cykl: Dict,
    surprise: Dict,
    event_risk: Dict,
    regime_type: str,
    range_warning: bool,
    flow_rezim: str,
    flow_score: int,
    flow_dywergencja: bool,
    scoring: Dict,
) -> Dict[str, Any]:
    """
    Łączy zmienne z wszystkich modułów w jedną zdefiniowaną SITUACJĘ.
    Zwraca: situation_id (kod), situation_label (opis PL), zmienne (dict wartosci).
    """
    zmienne = {
        "cot_momentum":     cot.get("momentum", "MIXED"),
        "cot_zscore":       round(cot.get("zscore", 0), 2),
        "cykl_faza":        cykl.get("phase", "UNKNOWN"),
        "cykl_zegar":       cykl.get("clock", "UNKNOWN"),
        "cykl_dojrzalosc":  cykl.get("maturity", "UNKNOWN"),
        "surprise_4w":      round(surprise.get("surprise_4w", 0), 2),
        "event_high_count": event_risk.get("high_count", 0),
        "event_risk_level": event_risk.get("risk_level", "NISKI"),
        "regime_typ":       regime_type or "NEUTRALNY",
        "regime_range":     range_warning,
        "flow_rezim":       flow_rezim or "NEUTRALNY",
        "flow_score":       flow_score,
        "flow_dywergencja": flow_dywergencja,
        "scoring_conviction": scoring.get("conviction", "PASS"),
        "scoring_bias":     scoring.get("bias", "CZEKAJ"),
    }

    # ---- Definicja sytuacji (logika łącząca zmienne) ----
    high_events = zmienne["event_high_count"]
    faza = zmienne["cykl_faza"]
    dojrzalosc = zmienne["cykl_dojrzalosc"]
    momentum = zmienne["cot_momentum"]
    surprise_4w = zmienne["surprise_4w"]

    if high_events >= 1 or zmienne["event_risk_level"] == "KRYTYCZNY":
        situation_id = "EVENT"
        situation_label = "Transakcja wokół wydarzenia makro – podwyższona zmienność"
    elif dojrzalosc == "LATE" and faza in ["SLOWDOWN", "CONTRACTION"]:
        situation_id = "LATE_CYCLE_RV"
        situation_label = "Późna faza cyklu – możliwy powrót do średniej / odwrócenie"
    elif momentum in ["BULLISH", "BEARISH"] and abs(surprise_4w) < 0.3:
        situation_id = "TREND_CORRECTION"
        situation_label = "Korekta w głównym trendzie instytucjonalnym (COT)"
    elif momentum == "MIXED" and abs(surprise_4w) < 0.5:
        situation_id = "RANGE_RV"
        situation_label = "Konsolidacja – powrót do średniej (range)"
    elif "RANGE" in (regime_type or "") or range_warning:
        situation_id = "RANGE_RV"
        situation_label = "Reżim range – ograniczony zasięg, mean reversion"
    else:
        situation_id = "TREND_CORRECTION"
        situation_label = "Korekta / trend – kontekst COT i cyklu"

    return {
        "situation_id":    situation_id,
        "situation_label": situation_label,
        "zmienne":         zmienne,
    }
