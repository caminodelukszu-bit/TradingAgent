# =============================================================================
# continuity_narrative.py - Ciągłość z poprzednim raportem: co się zmieniło i dlaczego
# Konkretne argumenty po polsku (COT+sentyment, stopy, dolar, euro, frank, kalendarz, makro).
# =============================================================================

from typing import Dict, Any, List, Optional
from datetime import datetime


def _decision_po_polsku(decision: str) -> str:
    if not decision:
        return "brak"
    if "NIE WCHODŹ" in decision.upper():
        return "CZEKAJ – nie wchodzić w nowe pozycje"
    if "OGRANICZENIAMI" in decision.upper():
        return "ostrożne wejście (ogranicz wielkość, 1–2 setupy)"
    if "WCHODŹ" in decision.upper() or "MOŻESZ" in decision.upper():
        return "można wchodzić (stosuj sugerowaną wielkość)"
    return decision


def _format_macro_value(val) -> str:
    if val is None:
        return "–"
    if isinstance(val, (int, float)):
        return str(round(val, 2))
    return str(val)


def get_previous_report():
    """Zwraca ostatni zapisany raport z archiwum (poprzedni run)."""
    try:
        from report_archive import list_reports
        reports = list_reports(limit=1)
        return reports[0] if reports else None
    except Exception:
        return None


def build_current_summary_for_diff(
    decision: str,
    wyniki: List[Dict],
    makro: Dict,
    instrukcja: Dict,
) -> Dict[str, Any]:
    """Buduje słownik 'current' w tym samym kształcie co zapis w archiwum (do diff_reports)."""
    macro_flat = {}
    if makro.get("DXY") and isinstance(makro["DXY"], dict):
        macro_flat["DXY"] = makro["DXY"].get("value")
    if makro.get("US10Y") and isinstance(makro["US10Y"], dict):
        macro_flat["US10Y"] = makro["US10Y"].get("value")
    if makro.get("FEDFUNDS") and isinstance(makro["FEDFUNDS"], dict):
        macro_flat["FED"] = makro["FEDFUNDS"].get("value")
    if makro.get("OIL_WTI") and isinstance(makro["OIL_WTI"], dict):
        macro_flat["OIL"] = makro["OIL_WTI"].get("value")
    signals = []
    for w in (wyniki or [])[:8]:
        signals.append({
            "instrument": w.get("instrument"),
            "bias": w.get("meta_bias"),
            "score": w.get("lacznie"),
            "conviction": w.get("conviction"),
        })
    return {
        "decision": decision,
        "summary": {
            "health": "OK",
            "signals": signals,
            "macro": macro_flat,
            "reasons": instrukcja.get("reasons", [])[:5],
            "ryzyka": instrukcja.get("ryzyka", [])[:3],
        },
    }


def build_continuity_narrative(
    current_decision: str,
    current_reasons: List[str],
    wyniki: List[Dict],
    makro: Dict,
    payload: Dict,
    previous_report: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Buduje narrację ciągłości po polsku: co się zmieniło, dlaczego, COT+sentyment, stopy, dolar, kalendarz.
    Zwraca dict z kluczami: naglowek, paragrafy (lista stringów), cot_sentyment, stopy_dolar, kalendarz, co_wzielismy.
    """
    out = {
        "naglowek": "Ciągłość z poprzednim raportem",
        "paragrafy": [],
        "analiza_kwartalna": "",
        "cot_sentyment": "",
        "stopy_dolar": "",
        "euro_frank_makro": "",
        "kalendarz": "",
        "komunikaty_oficjalne": "",
        "co_wzielismy": "",
    }
    # Analiza ostatnich ~123 raportów (kwartał) – wszystkie podlegają analizie przed wydaniem bieżącego
    try:
        from report_archive import get_reports_for_quarter
        from quarter_analysis import analyze_quarter_reports, QUARTER_REPORTS_LIMIT
        quarter_reports = get_reports_for_quarter(limit=QUARTER_REPORTS_LIMIT)
        quarter_result = analyze_quarter_reports(quarter_reports)
        out["analiza_kwartalna"] = quarter_result.get("summary_paragraph_pl", "")
    except Exception:
        pass
    instr = (payload or {}).get("instrukcja") or {}
    current_summary = build_current_summary_for_diff(
        current_decision, wyniki, makro, instr,
    )

    if not previous_report:
        out["paragrafy"].append(
            "To pierwszy raport w archiwum lub brak poprzedniego zapisu. "
            "Kolejne raporty będą porównywać się z tym i pokazywać, co się zmieniło i dlaczego."
        )
        out["co_wzielismy"] = (
            "Przy wniosku wzięliśmy pod uwagę: COT (pozycje instytucji), sentyment (retail), "
            "reżim techniczny, flow międzyrynkowy, zaskoczenia makro, wiadomości, kalendarz wydarzeń (USA, strefa euro, UK, itd.). "
            "Stopy procentowe (FED), dolar (DXY), obligacje (US10Y), ropa – cały kontekst makro."
        )
        _add_cot_sentiment_paragraph(wyniki, out)
        _add_macro_paragraph(makro, out)
        _add_calendar_paragraph(out)
        _add_official_headlines(out)
        return out

    prev_date = previous_report.get("report_date", "")
    prev_time = previous_report.get("report_time", "")
    prev_summary = previous_report.get("summary") or {}
    prev_decision = previous_report.get("decision", "")

    try:
        from report_archive import diff_reports
        diff = diff_reports(current_summary, previous_report)
    except Exception:
        diff = {}

    decyzja_teraz = _decision_po_polsku(current_decision)
    decyzja_wczesniej = _decision_po_polsku(prev_decision)

    # Nagłówek z datą poprzedniego
    out["paragrafy"].append(
        f"Poprzedni raport: {prev_date} o {prev_time}. Decyzja wtedy: {decyzja_wczesniej}."
    )

    if diff.get("decision_changed"):
        out["paragrafy"].append(
            f"W tym raporcie zmieniamy rekomendację: teraz {decyzja_teraz}. "
            "Poniżej konkretne powody (co wzięliśmy pod uwagę)."
        )
    else:
        out["paragrafy"].append(
            f"Zostajemy przy tej samej logice: {decyzja_teraz}. "
            "Kontekst makro i sygnały potwierdzają poprzednią ocenę – uzasadnienie poniżej."
        )

    # Konkretne uzasadnienie z reasons
    if current_reasons:
        out["paragrafy"].append("Dlaczego tak oceniamy:")
        for r in current_reasons[:4]:
            out["paragrafy"].append("• " + r)
    else:
        out["paragrafy"].append("Uzasadnienie: patrz sekcja „Wniosek inwestycyjny” oraz COT + sentyment poniżej.")

    # Zmiany w sygnałach
    if diff.get("signals_added"):
        out["paragrafy"].append(
            "Nowe rekomendacje w tym raporcie: " + ", ".join(diff["signals_added"]) + ". "
            "Pojawiły się setupy spełniające próg (COT, reżim, flow, brak blokady eventowej)."
        )
    if diff.get("signals_removed"):
        out["paragrafy"].append(
            "Z listy rekomendacji wypadły: " + ", ".join(diff["signals_removed"]) + ". "
            "Powód: zmiana kontekstu (np. reżim, event, słabszy scoring lub COT/sentyment)."
        )
    if diff.get("signals_changed"):
        for ch in diff["signals_changed"][:3]:
            prev_b = ch["prev"].get("bias") or "–"
            curr_b = ch["curr"].get("bias") or "–"
            prev_s = ch["prev"].get("score") or "–"
            curr_s = ch["curr"].get("score") or "–"
            out["paragrafy"].append(
                f"{ch['instrument']}: zmiana z {prev_b} (score {prev_s}) na {curr_b} (score {curr_s}) – "
                "zaktualizowany scoring (COT, reżim, flow lub wydarzenia)."
            )

    # Zmiany makro – konkretne liczby
    macro_changed = diff.get("macro_changed") or {}
    if macro_changed:
        frags = []
        if "DXY" in macro_changed:
            p, c = macro_changed["DXY"].get("prev"), macro_changed["DXY"].get("curr")
            frags.append(f"DXY: {_format_macro_value(p)} → {_format_macro_value(c)} (dolar)")
        if "US10Y" in macro_changed:
            p, c = macro_changed["US10Y"].get("prev"), macro_changed["US10Y"].get("curr")
            frags.append(f"obligacje 10Y: {_format_macro_value(p)}% → {_format_macro_value(c)}%")
        if "FED" in macro_changed:
            p, c = macro_changed["FED"].get("prev"), macro_changed["FED"].get("curr")
            frags.append(f"stopy FED: {_format_macro_value(p)}% → {_format_macro_value(c)}%")
        if "OIL" in macro_changed:
            p, c = macro_changed["OIL"].get("prev"), macro_changed["OIL"].get("curr")
            frags.append(f"ropa WTI: ${_format_macro_value(p)} → ${_format_macro_value(c)}")
        if frags:
            out["paragrafy"].append(
                "Zmiany makro od poprzedniego raportu: " + "; ".join(frags) + ". "
                "To wpływa na ocenę dolara, euro, franka i surowców – uwzględnione w obecnej rekomendacji."
            )

    _add_cot_sentiment_paragraph(wyniki, out)
    _add_macro_paragraph(makro, out)
    _add_calendar_paragraph(out)
    _add_official_headlines(out)
    _add_what_we_considered(out, payload)
    return out


def _add_cot_sentiment_paragraph(wyniki: List[Dict], out: Dict[str, Any]) -> None:
    """COT i sentyment zawsze w parze – jeden akapit po polsku."""
    top = [w for w in (wyniki or []) if w.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:4]
    if not top:
        out["cot_sentyment"] = (
            "COT i sentyment: brak sygnałów o wysokiej sile. "
            "Pozycje instytucji (COT) i sentyment retail nie dają obecnie wyraźnego układu – stąd rekomendacja CZEKAJ lub ostrożne wejście."
        )
        return
    lines = []
    for w in top:
        inst = w.get("instrument", "")
        cot_b = w.get("cot_bias", "")
        sent = w.get("sentiment")  # score lub opis
        bias = w.get("meta_bias", "")
        kier = "KUPNO" if bias == "BUY" else ("SPRZEDAZ" if bias == "SELL" else "neutralnie")
        lines.append(
            f"{inst}: COT wskazuje na {cot_b}; sentyment retail uwzględniony. "
            f"Rekomendacja: {kier} (łącznie COT + sentyment)."
        )
    out["cot_sentyment"] = " ".join(lines)


def _add_macro_paragraph(makro: Dict, out: Dict[str, Any]) -> None:
    """Stopy, dolar, euro, frank – czytelny akapit."""
    parts = []
    if makro.get("DXY") and isinstance(makro["DXY"], dict):
        v = makro["DXY"].get("value")
        tr = makro["DXY"].get("trend", "")
        trend_pl = "wzrost" if tr == "UP" else "spadek"
        parts.append(f"Dolar (DXY): {v} ({trend_pl})")
    if makro.get("US10Y") and isinstance(makro["US10Y"], dict):
        v = makro["US10Y"].get("value")
        parts.append(f"obligacje USA 10Y: {v}%")
    if makro.get("FEDFUNDS") and isinstance(makro["FEDFUNDS"], dict):
        v = makro["FEDFUNDS"].get("value")
        parts.append(f"stopy FED: {v}%")
    yc = makro.get("YIELD_CURVE")
    if yc is not None:
        parts.append(f"krzywa dochodowości (10Y-2Y): {yc:+.2f}")
    if makro.get("OIL_WTI") and isinstance(makro["OIL_WTI"], dict):
        v = makro["OIL_WTI"].get("value")
        parts.append(f"ropa WTI: ${v}")
    if parts:
        out["stopy_dolar"] = "Kontekst makro (USA, stopy, dolar, ropa): " + "; ".join(parts) + ". Wpływ na EUR, CHF i surowce (AUD, CAD) jest uwzględniony w rekomendacjach."
    # Euro / frank – jeśli mamy w sygnałach
    out["euro_frank_makro"] = "Euro i frank szwajcarski oceniamy w kontekście dolara i stóp (FED, EBC/SNB). Zmienność przed ważnymi datami (NFP, FOMC, CPI) jest uwzględniona w ryzyku."


def _add_calendar_paragraph(out: Dict[str, Any]) -> None:
    """Nadchodzące wydarzenia – globalnie (USA, EUR, UK, itd.)."""
    try:
        from event_calendar import get_upcoming_events_summary
        global_events = get_upcoming_events_summary(currency=None, days_ahead=7, max_events=12)
        if global_events:
            out["kalendarz"] = (
                "Kalendarz (najbliższe 7 dni): " + global_events + ". "
                "Wydarzenia wysokiej wagi (NFP, FOMC, CPI, decyzje banków centralnych) wpływają na zmienność – przy rekomendacjach uwzględniamy ryzyko eventowe (USA, strefa euro, UK, itd.)."
            )
        else:
            out["kalendarz"] = "Brak wysokowagowych wydarzeń w kalendarzu w najbliższych dniach. Ryzyko eventowe niskie."
    except Exception:
        out["kalendarz"] = "Kalendarz wydarzeń (ForexFactory): uwzględniany przy ocenie ryzyka; sprawdź aktualny kalendarz przed wejściem."


def _add_official_headlines(out: Dict[str, Any]) -> None:
    """Komunikaty oficjalne (banki centralne, wybrane źródła) – krótkie podsumowanie."""
    try:
        from official_sources import get_summary_for_report
        s = get_summary_for_report(max_items=5)
        if s:
            out["komunikaty_oficjalne"] = s
    except Exception:
        out["komunikaty_oficjalne"] = ""


def _add_what_we_considered(out: Dict[str, Any], payload: Dict) -> None:
    """Co wzięliśmy pod uwagę – cały świat w miarę danych."""
    out["co_wzielismy"] = (
        "Przy tym raporcie wzięliśmy pod uwagę: "
        "COT (pozycje instytucji) i sentyment (retail) zawsze razem; "
        "stopy procentowe (FED, EBC, BOE, BOJ, BOC, SNB) i ich wpływ na dolar, euro, frank, funt; "
        "dolar (DXY), obligacje (US10Y), krzywą dochodowości, ropę; "
        "reżim techniczny i flow międzyrynkowy; zaskoczenia makro; wiadomości; "
        "kalendarz wydarzeń (USA, strefa euro, UK, Chiny, Kanada, Szwajcaria, Japonia – w miarę dostępności danych). "
        "Ryzyko geopolityczne i zmienność kursów są uwzględniane przez kary eventowe i ograniczenie wielkości pozycji. "
        "Raport nie gwarantuje trafności – wykorzystaliśmy wszystkie dostępne warstwy analizy, aby wspomóc Twoją decyzję."
    )
