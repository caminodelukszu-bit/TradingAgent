# =============================================================================
# commentary_engine.py - SofikaMax Agent
# Komentarz jak od profesjonalnego doradcy: synteza kontekstu rynku i wnioski.
# Z opcją LLM + RAG (few-shot); fallback na szablon.
# =============================================================================

from typing import List, Dict, Any
from datetime import datetime

# Few-shot: przykłady dobrego komentarza (struktura: Kontekst, Flow, Rekomendacja, Ryzyka)
FEW_SHOT_SYSTEM = """Jesteś analitykiem rynku FX/commodities w stylu SofikaMax Agent. Piszesz krótki, konkretny komentarz (2-4 akapity) po polsku.
Struktura: **Kontekst rynku:** (DXY, stopy, krzywa, ropa/złoto). **Flow:** (rezim cross-asset, USD, surowce, BTC). **Rekomendacja:** (co na czoło, horyzont 2-4 tyg., bez rekomendacji inwestycyjnej). **Ryzyka:** (koncentracja, eventy, lub standardowe). Opcjonalnie **Weryfikacja sygnałów:** jeśli są dane.
Ton: profesjonalny, ostrożny, COT/sygnały traktowane jako kontekst, nie prognoza."""

FEW_SHOT_EXAMPLES = """
Przykład 1:
**Kontekst rynku:** Dolar (DXY 104.2) pod presją. Obligacje 10Y na poziomie 4.1%. Ujemny real yield wspiera złoto.
**Flow:** Rezim cross-asset: risk-on, USD: słaby. Surowce w górę – wsparcie dla AUD/CAD.
**Rekomendacja:** Na czoło wysuwają się: EUR (72/100), AUD (68/100). Kontekst do analizy technicznej i zarządzania ryzykiem. Horyzont 2–4 tygodnie.
**Ryzyka:** Standardowe – stosuj limity i dywersyfikację.

Przykład 2:
**Kontekst rynku:** DXY umacnia się, 10Y stabilne. Ropa WTI ok. $78 – istotna dla CAD.
**Flow:** Rezim: neutralny, USD: umiarkowanie mocny.
**Rekomendacja:** Brak wyraźnych setupów o wysokiej conviction. Czekaj na lepsze potwierdzenie (COT, regime, flow).
**Ryzyka:** W kalendarzu wydarzenia wysokiej wagi – zmniejsz ekspozycję przed danymi.
"""


def _build_current_context(
    wyniki: List[Dict],
    makro: Dict,
    flow_globalny: Dict,
    risk: Dict,
    verified: List[Dict],
) -> str:
    """Strukturyzowany kontekst bieżącego raportu do promptu."""
    lines = []
    dxy = makro.get("DXY", {}) if isinstance(makro.get("DXY"), dict) else {}
    lines.append(f"DXY: {dxy.get('value')} trend {dxy.get('trend', '')} | US10Y: {makro.get('US10Y', {}).get('value') if isinstance(makro.get('US10Y'), dict) else '?'} | YIELD_CURVE: {makro.get('YIELD_CURVE')} | OIL: {makro.get('OIL_WTI', {}).get('value') if isinstance(makro.get('OIL_WTI'), dict) else '?'}")
    lines.append(f"Flow: rezim={flow_globalny.get('rezim')} USD={flow_globalny.get('usd_kierunek')} surowce={flow_globalny.get('surowce_kierunek')} BTC={flow_globalny.get('crypto', {}).get('btc_trend')}")
    top = [w for w in wyniki if w.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:5]
    lines.append("Top conviction: " + ", ".join([f"{w['instrument']} {w['lacznie']}/100 ({w.get('situation_label', '')})" for w in top]) if top else "Top conviction: brak")
    lines.append(f"Risk: {risk.get('rekomendacja', '')} | ostrzezenia: {risk.get('ostrzezenia', [])}")
    if verified:
        hit = sum(1 for v in verified if v.get("hit"))
        lines.append(f"Weryfikacja ostatnich {len(verified)}: {hit}/{len(verified)} trafionych.")
    return "\n".join(lines)


def generate(
    wyniki: List[Dict],
    makro: Dict,
    flow_globalny: Dict,
    risk: Dict,
    pary_usd: List[Dict],
    pary_cross: List[Dict],
    verified: List[Dict] = None,
) -> str:
    """
    Generuje 2-4 akapity komentarza analityka. Gdy skonfigurowany LLM + RAG – używa ich (few-shot);
    w przeciwnym razie lub przy błędzie – szablon (rule-based).
    """
    verified = verified or []
    try:
        from llm_engine import is_available, generate as llm_generate
        from rag_store import get_context_for_llm
        from config import RAG_CONTEXT_ITEMS
    except ImportError:
        return _generate_rule_based(wyniki, makro, flow_globalny, risk, pary_usd, pary_cross, verified)

    if not is_available():
        return _generate_rule_based(wyniki, makro, flow_globalny, risk, pary_usd, pary_cross, verified)

    current = _build_current_context(wyniki, makro, flow_globalny, risk, verified)
    rag = get_context_for_llm(limit=RAG_CONTEXT_ITEMS)
    user_prompt = "Dane bieżącego raportu:\n" + current
    if rag:
        user_prompt += "\n\nKontekst z historii (RAG):\n" + rag
    user_prompt += "\n\nNapisz komentarz analityka (2-4 akapity, po polsku, ta sama struktura co w przykładach). Tylko komentarz, bez nagłówków typu 'Komentarz:'."

    system_prompt = FEW_SHOT_SYSTEM + FEW_SHOT_EXAMPLES
    out = llm_generate(system_prompt=system_prompt, user_prompt=user_prompt)
    if out and len(out.strip()) > 50:
        return out.strip()
    return _generate_rule_based(wyniki, makro, flow_globalny, risk, pary_usd, pary_cross, verified)


def _generate_rule_based(
    wyniki: List[Dict],
    makro: Dict,
    flow_globalny: Dict,
    risk: Dict,
    pary_usd: List[Dict],
    pary_cross: List[Dict],
    verified: List[Dict],
) -> str:
    """Komentarz z szablonu (fallback gdy brak LLM lub błąd)."""
    parts = []

    # ---- 1. Kontekst makro ----
    dxy = makro.get("DXY", {}).get("value") if isinstance(makro.get("DXY"), dict) else None
    dxy_trend = makro.get("DXY", {}).get("trend", "") if isinstance(makro.get("DXY"), dict) else ""
    us10 = makro.get("US10Y", {}).get("value") if isinstance(makro.get("US10Y"), dict) else None
    curve = makro.get("YIELD_CURVE")
    fed = makro.get("FEDFUNDS", {}).get("value") if isinstance(makro.get("FEDFUNDS"), dict) else None
    oil = makro.get("OIL_WTI", {}).get("value") if isinstance(makro.get("OIL_WTI"), dict) else None
    real_y = makro.get("REAL_YIELD_10Y")

    ctx = []
    if dxy is not None:
        ctx.append(f"Dolar (DXY {dxy}) {'wzmacnia się' if dxy_trend == 'UP' else 'pod presją'}.")
    if us10 is not None:
        ctx.append(f"Obligacje 10Y na poziomie {us10}%.")
    if curve is not None:
        ctx.append("Krzywa dochodowości w strefie normalnej." if curve > 0 else "Uwaga: krzywa odwrócona.")
    if real_y is not None and real_y < 0:
        ctx.append("Ujemny real yield wspiera złoto i aktywa realne.")
    if oil is not None:
        ctx.append(f"Ropa WTI ok. ${oil} – istotna dla CAD i walut surowcowych.")

    if ctx:
        parts.append("**Kontekst rynku:** " + " ".join(ctx))

    # ---- 2. Flow i dominujący temat ----
    rezim = flow_globalny.get("rezim", "NEUTRALNY")
    usd_k = flow_globalny.get("usd_kierunek", "NEUTRALNY")
    surowce = flow_globalny.get("surowce_kierunek", "")
    btc = flow_globalny.get("crypto", {}).get("btc_trend", "")

    flow_txt = f"Rezim cross-asset: {rezim}, USD: {usd_k}."
    if surowce:
        flow_txt += f" Surowce: {surowce} – wsparcie dla AUD/CAD przy silnym popycie."
    if btc and btc != "NEUTRALNY":
        flow_txt += f" BTC ({btc}) – odzwierciedla apetyt na ryzyko."
    parts.append("**Flow:** " + flow_txt)

    # ---- 3. Rekomendacja (co robić, na co uważać) ----
    top = [w for w in wyniki if w.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:3]
    if top:
        names = ", ".join([f"{w['instrument']} ({w['lacznie']}/100)" for w in top])
        parts.append(
            f"**Rekomendacja:** W obecnym ustawieniu na czoło wysuwają się: {names}. "
            "Traktuj to jako kontekst do dalszej analizy technicznej i zarządzania ryzykiem – "
            "nie jako sygnał do wejścia bez własnej weryfikacji. Horyzont 2–4 tygodnie spójny z fazą cyklu."
        )
    else:
        parts.append(
            "**Rekomendacja:** Brak wyraźnych setupów o wysokiej conviction. "
            "Racjonalne jest czekanie na lepsze potwierdzenie (COT, regime, flow) zamiast wymuszania pozycji."
        )

    # ---- 4. Ryzyka ----
    risk_txt = []
    if risk.get("ostrzezenia"):
        risk_txt.append("Koncentracja w grupach korelacyjnych – ogranicz liczbę równoległych pozycji w tej samej grupie.")
    events = any(
        w.get("event_risk") in ("WYSOKI", "KRYTYCZNY")
        for w in wyniki
    )
    if events:
        risk_txt.append("W kalendarzu wydarzenia wysokiej wagi – zmniejsz ekspozycję lub unikaj wejść tuż przed danymi.")
    if risk_txt:
        parts.append("**Ryzyka:** " + " ".join(risk_txt))
    else:
        parts.append("**Ryzyka:** Standardowe – stosuj limity i dywersyfikację.")

    # ---- 5. Ostatnie weryfikacje (uczenie) ----
    if verified:
        hit_count = sum(1 for v in verified if v.get("hit"))
        total = len(verified)
        parts.append(
            f"**Weryfikacja sygnałów (ostatnie {total}):** "
            f"{hit_count}/{total} trafionych kierunkowo w horyzoncie ~2 tygodni. "
            "Wnioski: system działa kontekstowo; wyniki zależą od fazy rynku i realizacji makro."
        )

    return "\n\n".join(parts)


def generate_short_for_telegram(
    wyniki: List[Dict],
    makro: Dict,
    flow_globalny: Dict,
    verified: List[Dict] = None,
) -> str:
    """Krótka wersja komentarza (2-3 zdania) na Telegram."""
    verified = verified or []
    top = [w for w in wyniki if w.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:2]
    dxy_t = makro.get("DXY", {}).get("trend", "") if isinstance(makro.get("DXY"), dict) else ""
    usd_k = flow_globalny.get("usd_kierunek", "NEUTRALNY")

    s = "Komentarz: "
    s += "Dolar " + ("mocniejszy" if dxy_t == "UP" else "słabszy") + f", flow USD: {usd_k}. "
    if top:
        s += f"Na czoło: {top[0]['instrument']} ({top[0]['lacznie']}/100). "
    if verified:
        hit = sum(1 for v in verified[:5] if v.get("hit"))
        s += f"Ostatnia weryfikacja: {hit}/{min(5, len(verified))} trafionych. "
    s += "COT jest kontekstem, nie prognozą."
    return s
