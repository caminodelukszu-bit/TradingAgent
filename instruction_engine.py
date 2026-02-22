# =============================================================================
# instruction_engine.py - SofikaMax Agent
# Jednoznaczna instrukcja: WCHODZIĆ / NIE WCHODZIĆ / WCHODZIĆ Z OGRANICZENIAMI.
# Uzasadnienie, sugerowany size, rationale per sygnał. Agent dba o kapitał.
# =============================================================================

from typing import List, Dict, Any, Tuple

# Jakość sytuacji (z feedback_analyzer)
QUALITY_GOOD = 1.0
QUALITY_BAD = 0.0


def get_primary_driver(w: Dict[str, Any]) -> str:
    """
    Główny driver sygnału: COT / MACRO / REGIME / FLOW / EVENT.
    Do argumentacji i zapisu rationale.
    """
    if w.get("event_risk") in ("WYSOKI", "KRYTYCZNY"):
        return "EVENT"
    if w.get("range_warning") or "RANGE" in (w.get("typ_rezimu") or ""):
        return "REGIME"
    sz = w.get("szczegoly") or {}
    cot = sz.get("cot", 0) or 0
    flow = sz.get("flow", 10) or 10
    cykl = sz.get("cykl", 0) or 0
    if cot >= 16 and w.get("cot_obj", {}).get("extreme_warning"):
        return "COT"
    if flow <= 5 or flow >= 16:
        return "FLOW"
    if cykl >= 14 or (w.get("faza") and w.get("faza") != "N/A"):
        return "MACRO"
    if cot >= 14:
        return "COT"
    return "MACRO"


def build_rationale(para: str, kierunek: str, w: Dict[str, Any], primary_driver: str) -> str:
    """
    Jedno zdanie uzasadnienia: co jest podstawą sygnału i ewentualny caveat (event).
    Kierunek: LONG / SHORT. Agent dba o kapitał – przy evencie zawsze caveat.
    """
    kier_pl = "Long" if kierunek == "LONG" else "Short"
    base = f"{kier_pl} {para}"
    event_risk = w.get("event_risk", "NISKI")
    regime = w.get("typ_rezimu", "") or ""
    if primary_driver == "EVENT":
        return f"{base}: ryzyko wydarzenia makro – wejdź po ogłoszeniu lub pomiń."
    if primary_driver == "COT":
        conf = "ekstremum COT" if (w.get("cot_obj") or {}).get("extreme_warning") else "momentum COT"
        if event_risk in ("WYSOKI", "KRYTYCZNY"):
            return f"{base}: {conf}, potwierdzenie flow. Przed wydarzeniem – ogranicz size lub czekaj."
        return f"{base}: {conf}, potwierdzenie flow i reżim."
    if primary_driver == "REGIME":
        if event_risk in ("WYSOKI", "KRYTYCZNY"):
            return f"{base}: reżim {regime[:20]}. Przed wydarzeniem – max 0.5% kapitału."
        return f"{base}: reżim {regime[:20]}. Ogranicz size (range/konieczność potwierdzenia)."
    if primary_driver == "FLOW":
        if event_risk in ("WYSOKI", "KRYTYCZNY"):
            return f"{base}: flow intermarket. Przed wydarzeniem – ogranicz size."
        return f"{base}: flow intermarket, potwierdzenie reżimu."
    # MACRO
    if event_risk in ("WYSOKI", "KRYTYCZNY"):
        return f"{base}: cykl/makro. Przed wydarzeniem – ogranicz size lub wejdź po danych."
    return f"{base}: cykl i makro, potwierdzenie techniczne."


def suggested_size_pct(
    conviction: str,
    quality: float,
    event_risk_level: str,
) -> Tuple[float, str]:
    """
    Sugerowany size (% kapitału) i krótki opis dlaczego.
    Zwraca (procent 0.25–1.5, opis).
    """
    # PASS / brak = nie otwieraj nowej pozycji (spec instytucjonalna)
    if conviction in ("PASS", "") or conviction not in ("WYSOKI", "UMIARKOWANY", "NISKI"):
        return (0.0, "Tylko watchlist – nie otwieraj nowej pozycji.")
    mult_conv = {"WYSOKI": 1.0, "UMIARKOWANY": 0.7, "NISKI": 0.5}.get(conviction, 0.5)
    mult_quality = 1.0 if quality >= 0.99 else (0.7 if quality >= 0.4 else 0.5)
    event_penalty = 0.0
    event_note = ""
    if event_risk_level in ("KRYTYCZNY", "WYSOKI"):
        event_penalty = 0.5 if event_risk_level == "KRYTYCZNY" else 0.3
        event_note = " (wydarzenie w ciągu 24–72h – ogranicz)" if event_risk_level == "KRYTYCZNY" else " (wydarzenie w tygodniu)"
    pct = 1.0 * mult_conv * mult_quality * (1.0 - event_penalty)
    pct = max(0.25, min(1.5, round(pct * 4) / 4))  # 0.25 kroki
    if event_note:
        desc = f"{pct}% kapitału{event_note}"
    elif quality <= 0.01:
        desc = f"{pct}% kapitału (niska trafność historyczna – ostrożnie)"
    else:
        desc = f"{pct}% kapitału"
    return (pct, desc)


def build_instruction(
    wyniki: List[Dict],
    pary_usd: List[Dict],
    risk: Dict[str, Any],
    feedback: Dict[str, Any],
    workflow_lines: List[Dict],
    situation_quality_map: Dict[str, float],
) -> Dict[str, Any]:
    """
    Zwraca jedną czytelną instrukcję: decyzja (WCHODŹ / NIE WCHODŹ / WCHODŹ Z OGRANICZENIAMI),
    uzasadnienie, top pomysły z size i rationale, ryzyka.
    Priorytet: ochrona kapitału – w razie wątpliwości NIE WCHODŹ lub OGRANICZENIA.
    """
    reasons: List[str] = []
    situation_types_low = set(feedback.get("situation_types_low") or [])
    quality_map = situation_quality_map or {}
    wyniki_by_inst = {w["instrument"]: w for w in wyniki}
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}

    # Czy którykolwiek top sygnał ma event KRYTYCZNY?
    top_paras = [p.get("para") for p in (pary_usd or [])[:6]]
    any_critical = False
    any_high_event = False
    for p in (pary_usd or [])[:6]:
        para = p.get("para", "")
        inst = nazwa_do_inst.get(para, para.split("/")[0] if "/" in para else "")
        w = wyniki_by_inst.get(inst, {})
        er = w.get("event_risk", "NISKI")
        if er == "KRYTYCZNY":
            any_critical = True
        if er in ("WYSOKI", "KRYTYCZNY"):
            any_high_event = True

    # Czy mamy choć jeden sensowny setup (wysoka conviction, dobra jakość)?
    good_setups = 0
    for line in (workflow_lines or [])[:5]:
        conv = line.get("conviction", "")
        q = quality_map.get(line.get("situation_id", ""), 0.5)
        if conv in ("WYSOKI", "UMIARKOWANY") and q >= 0.5:
            good_setups += 1

    # DECYZJA
    if any_critical:
        decision = "NIE WCHODŹ"
        reasons.append("Wydarzenie wysokiej wagi w ciągu 24h – agent chroni kapitał. Wejdź po ogłoszeniu lub jutro.")
    elif not good_setups:
        decision = "NIE WCHODŹ"
        reasons.append("Brak setupów o wystarczającej conviction i jakości. Nie wymuszaj – czekaj na lepszy kontekst.")
    elif any_high_event or risk.get("ostrzezenia"):
        decision = "WCHODŹ Z OGRANICZENIAMI"
        if any_high_event:
            reasons.append("Wydarzenie makro w tym tygodniu – zmniejsz size (max 0.5–0.75% na pozycję) lub wejdź po danych.")
        if risk.get("ostrzezenia"):
            reasons.append("Ogranicz liczbę pozycji w tej samej grupie korelacyjnej (max 2 na grupę).")
        reasons.append("Wybierz 1–2 najlepsze setupy z listy poniżej; nie otwieraj wszystkich.")
    else:
        decision = "WCHODŹ"
        reasons.append("Warunki na wejście spełnione. Max " + str(risk.get("max_pozycje", 5)) + " równoczesnych pozycji.")
        reasons.append("Tylko setupy HIGH i MOD – NISKI/PASS to watchlist (nie otwieraj nowej pozycji).")
        reasons.append("Stosuj sugerowany size i nie przekraczaj ekspozycji w jednej grupie.")

    # Enrich workflow lines with suggested_pct, rationale, primary_driver
    enriched_lines: List[Dict] = []
    for line in (workflow_lines or []):
        para = line.get("para", "")
        kierunek = line.get("kierunek", "LONG")
        inst = nazwa_do_inst.get(para, para.split("/")[0] if "/" in para else "")
        w = wyniki_by_inst.get(inst, {})
        event_level = w.get("event_risk", "NISKI")
        primary_driver = get_primary_driver(w)
        rationale = build_rationale(para, kierunek, w, primary_driver)
        q = quality_map.get(line.get("situation_id", ""), 0.5)
        conv = line.get("conviction", "")
        pct, size_desc = suggested_size_pct(conv, q, event_level)
        enriched_lines.append({
            **line,
            "primary_driver": primary_driver,
            "rationale": rationale,
            "suggested_pct": pct,
            "suggested_size_desc": size_desc,
        })

    # Top pomysły (jeśli wchodzić) – tylko WYSOKI i UMIARKOWANY (PASS/NISKI = watchlist, nie otwieraj)
    tradeable = [line for line in enriched_lines if line.get("conviction") in ("WYSOKI", "UMIARKOWANY")]
    top_ideas = [
        {
            "co": line["co"],
            "suggested_pct": line["suggested_pct"],
            "suggested_size_desc": line["suggested_size_desc"],
            "rationale": line["rationale"],
        }
        for line in tradeable[:3]
    ]

    # Ryzyka (do wyświetlenia w instrukcji)
    ryzyka: List[str] = list(risk.get("ostrzezenia", []))
    if any_high_event:
        ryzyka.insert(0, "Wydarzenie makro w najbliższych dniach – podwyższona zmienność i ryzyko slippage.")
    if situation_types_low and good_setups:
        ryzyka.append("Część setupów ma historycznie niską trafność – stosuj sugerowany (mniejszy) size.")

    return {
        "decision": decision,
        "reasons": reasons,
        "top_ideas": top_ideas,
        "ryzyka": ryzyka,
        "workflow_lines_enriched": enriched_lines,
    }
