# =============================================================================
# workflow_engine.py - SofikaMax Agent
# Jasna informacja: CO handlować i JAK DŁUGO. Dwa warianty analizy per sygnał.
# =============================================================================

from typing import List, Dict, Any


def build_workflow(
    wyniki: List[Dict],
    pary_usd: List[Dict],
    top_n: int = 5,
    situation_quality_map: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """
    Dla każdego z top sygnałów zwraca jedną linię workflow:
    co handlować, jak długo, wariant A, wariant B, sytuacja.
    Jeśli podano situation_quality_map (z feedbacku), workflow jest sortowany
    po jakości (najpierw historycznie trafne), z adnotacją quality_note.
    """
    top_pary = sorted(pary_usd, key=lambda x: x.get("sila_sygnalu", 0), reverse=True)[:top_n]
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}
    wyniki_by_inst = {w["instrument"]: w for w in wyniki}
    quality_map = situation_quality_map or {}

    lines = []
    for p in top_pary:
        para = p.get("para", "")
        inst = nazwa_do_inst.get(para, para.split("/")[0] if "/" in para else "")
        w = wyniki_by_inst.get(inst, {})
        situation_id = w.get("situation_id", "OTHER")
        situation_label = w.get("situation_label", w.get("meta_type", ""))
        conviction = p.get("learned_conviction") or p.get("conviction", "")
        quality = quality_map.get(situation_id, 0.5)
        if quality >= 0.99:
            quality_note = "Historycznie trafne"
        elif quality <= 0.01:
            quality_note = "Uwaga: niska trafność historyczna"
        else:
            quality_note = ""
        lines.append({
            "para":         para,
            "kierunek":     p.get("kierunek", ""),
            "co":           f"{para} {p.get('kierunek','')}",
            "jak_dlugo":    w.get("meta_horizon", "2-4w"),
            "wariant_a":    w.get("wariant_a", ""),
            "wariant_b":    w.get("wariant_b", ""),
            "sytuacja":     situation_label,
            "situation_id": situation_id,
            "conviction":   conviction,
            "quality":      quality,
            "quality_note": quality_note,
        })
    # Sortowanie: najpierw wysokiej jakości (1.0), potem neutral (0.5), na końcu niska (0.0)
    lines.sort(key=lambda x: -x["quality"])
    return lines
