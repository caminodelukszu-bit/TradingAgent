# ============================================================
# SofikaMax Agent - Telegram Bot
# Profesjonalne raporty: system health, sygnaly, makro, opcjonalnie zalacznik .md
# Lista odbiorcow = subskrybenci z bazy (subscription_store). Fallback: AUTORYZOWANI z config.
# ============================================================

import requests
import io
import os
import traceback
from datetime import datetime

# Marka agenta
AGENT_NAME = "SofikaMax Agent"

# Sciezka do logu bledow PDF (zeby wiedziec, dlaczego raport przychodzi jako tekst zamiast PDF)
def _log_pdf_error(exc: Exception):
    """Zapisuje wyjatek PDF do data/pdf_error.log – przy raporcie z harmonogramu wiadomo, czemu nie ma PDF."""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "pdf_error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{type(exc).__name__}: {exc}\n")
            traceback.print_exc(file=f)
        print(f"   [PDF] Szczegoly bledu zapisane w: {log_path}")
    except Exception:
        pass

# ============================================================
# KONFIGURACJA
# ============================================================
TOKEN = "8300117787:AAGeNiOIUwcXCvaYwLmzSm2_JhbsGb2JpeQ"
# Fallback gdy baza subskrypcji jest pusta (np. pierwsze uruchomienie)
AUTORYZOWANI = [
    6055734304,   # Lukasz (administrator)
]


def get_recipients() -> list:
    """Lista chat_id do ktorych wysylac raporty: aktywni subskrybenci z bazy; jesli baza pusta – AUTORYZOWANI."""
    try:
        from subscription_store import get_active_subscribers
        ids = get_active_subscribers()
        if ids:
            return ids
    except Exception:
        pass
    return list(AUTORYZOWANI)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def wyslij_wiadomosc(chat_id: int, tekst: str) -> bool:
    url  = f"{BASE_URL}/sendMessage"
    data = {
        "chat_id":    chat_id,
        "text":       tekst,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            return True
        print(f"   Blad wysylania do {chat_id}: {r.text[:100]}")
        return False
    except Exception as e:
        print(f"   Blad polaczenia: {e}")
        return False


def wyslij_dokument(chat_id: int, nazwa_pliku: str, tresc: str, caption: str = "") -> bool:
    """Wysyla plik (np. daily_report.md) do chatu."""
    url = f"{BASE_URL}/sendDocument"
    try:
        bio = io.BytesIO(tresc.encode("utf-8"))
        bio.name = nazwa_pliku
        files = {"document": (nazwa_pliku, bio, "text/markdown")}
        data = {"chat_id": chat_id, "caption": caption[:1024] if caption else ""}
        r = requests.post(url, data=data, files=files, timeout=15)
        if r.status_code == 200:
            return True
        print(f"   Blad wysylania dokumentu: {r.text[:100]}")
        return False
    except Exception as e:
        print(f"   Blad wysylania dokumentu: {e}")
        return False


def wyslij_dokument_bytes(
    chat_id: int,
    nazwa_pliku: str,
    bytes_content: bytes,
    caption: str = "",
    mime_type: str = "application/pdf",
) -> bool:
    """Wysyła plik binarny (np. PDF) do chatu – jako dokument do pobrania."""
    if not bytes_content or len(bytes_content) < 100:
        print("   [sendDocument] Pominieto: plik pusty lub za maly.")
        return False
    # Telegram rozpoznaje typ po rozszerzeniu; wymagane .pdf do pobrania jako PDF
    if mime_type == "application/pdf" and not nazwa_pliku.lower().endswith(".pdf"):
        nazwa_pliku = nazwa_pliku.rstrip() + ".pdf"
    url = f"{BASE_URL}/sendDocument"
    try:
        bio = io.BytesIO(bytes_content)
        bio.seek(0)  # wymagane – requests czyta od bieżącej pozycji
        files = {"document": (nazwa_pliku, bio, mime_type)}
        data = {"chat_id": chat_id, "caption": (caption[:1024] if caption else "")}
        r = requests.post(url, data=data, files=files, timeout=30)
        if r.status_code == 200:
            return True
        out = r.text[:300] if r.text else ""
        print(f"   [sendDocument] Blad {r.status_code} do {chat_id}: {out}")
        return False
    except Exception as e:
        print(f"   [sendDocument] Wyjatek: {e}")
        return False


def wyslij_do_wszystkich(tekst: str):
    recipients = get_recipients()
    print(f"\n   Wysylam do {len(recipients)} odbiorcow (subskrybenci)...")
    sukces = 0
    for chat_id in recipients:
        if wyslij_wiadomosc(chat_id, tekst):
            print(f"   Wyslano do: {chat_id}")
            sukces += 1
    print(f"   Wyslano: {sukces}/{len(recipients)}")


def _system_health(wyniki: list, blad_flow: bool = False, blad_regime: bool = False) -> tuple:
    """Zwraca (status_str, czy_ok). status_str np. ALL_GREEN lub WARNING."""
    issues = []
    if blad_flow:
        issues.append("Flow")
    if blad_regime:
        issues.append("Regime")
    if not wyniki or len(wyniki) < 5:
        issues.append("Dane")
    if not issues:
        return "ALL_GREEN", True
    return "WARNING: " + ", ".join(issues), False


def formatuj_raport_telegram(wyniki: list, makro: dict, tryb: str, health_status: str = "ALL_GREEN", payload: dict = None) -> str:
    teraz = datetime.now().strftime("%d.%m.%Y %H:%M")
    godzina = datetime.now().hour
    if godzina < 10:
        pora = "Raport poranny"
    elif godzina < 15:
        pora = "Raport poludniowy"
    elif godzina < 20:
        pora = "Raport wieczorny"
    else:
        pora = "Raport nocny"

    n_inst = len(wyniki) if wyniki else 0
    health_color = "green" if health_status == "ALL_GREEN" else "orange"
    health_emoji = "OK" if health_status == "ALL_GREEN" else "!"

    tekst  = f"<b>{AGENT_NAME}</b>\n"
    tekst += f"{pora} | {teraz}\n"
    tekst += "────────────────────────────\n"
    tekst += f"<b>SYSTEM HEALTH:</b> {health_status}\n"
    tekst += f"Dataset: {n_inst} instrumentow | Zrodla: 6/6 warstw\n"
    tekst += "────────────────────────────\n\n"

    # INSTRUKCJA – decyzja i uzasadnienie (na górze, agent dba o kapitał)
    instr = (payload or {}).get("instrukcja") or {}
    if instr:
        decision = instr.get("decision") or "WCHODŹ Z OGRANICZENIAMI"
        if decision == "NIE WCHODŹ":
            tekst += "<b>INSTRUKCJA: NIE WCHODŹ</b> w nowe pozycje.\n"
        elif decision == "WCHODŹ Z OGRANICZENIAMI":
            tekst += "<b>INSTRUKCJA: WCHODŹ Z OGRANICZENIAMI</b> (zmniejsz size, 1–2 setupy).\n"
        else:
            tekst += "<b>INSTRUKCJA: MOŻESZ WCHODZIĆ</b> (stosuj sugerowany size).\n"
        for r in instr.get("reasons", [])[:3]:
            tekst += f"• {r}\n"
        top_ideas = instr.get("top_ideas", [])[:2]
        if top_ideas:
            tekst += "\n<b>Jeśli wchodzisz:</b>\n"
            for i, idea in enumerate(top_ideas, 1):
                tekst += f"{i}. {idea.get('co','')} | {idea.get('suggested_size_desc','')}\n"
                tekst += f"   {idea.get('rationale','')}\n"
        if instr.get("ryzyka"):
            tekst += "\n<b>Ryzyka:</b> " + "; ".join(instr["ryzyka"][:2]) + "\n"
        tekst += "────────────────────────────\n\n"

    top = [w for w in wyniki if w.get("conviction") in ["WYSOKI", "UMIARKOWANY"]] if wyniki else []

    if top:
        tekst += "<b>AKTYWNE SYGNALY</b>\n\n"
        for w in top[:3]:
            ikona = "BUY" if w.get("meta_bias") == "BUY" else ("SELL" if w.get("meta_bias") == "SELL" else "NEUTRAL")
            tekst += f"<b>{w['instrument']} - {ikona}</b>\n"
            tekst += f"Score: {w['lacznie']}/100 | {w['conviction']}\n"
            tekst += f"Type: {w.get('meta_type','?')} | Horyzont: {w.get('meta_horizon','?')}\n"
            tekst += f"Faza: {w.get('faza','?')} | {w.get('zegar','?')}\n\n"
    else:
        tekst += "<b>BRAK SYGNALOW</b>\n"
        tekst += "Czekaj na lepszy setup. Nie wymuszaj transakcji.\n\n"
        if wyniki:
            n = wyniki[0]
            tekst += f"Najblizszy: {n['instrument']} ({n['lacznie']}/100)\n\n"

    tekst += "────────────────────────────\n"
    tekst += "<b>MAKRO</b>\n"
    if makro.get("DXY"):
        trend = "+" if makro["DXY"]["trend"] == "UP" else "-"
        tekst += f"DXY: {makro['DXY']['value']} ({trend})  "
    if makro.get("US10Y"):
        tekst += f"US10Y: {makro['US10Y']['value']}%\n"
    if makro.get("YIELD_CURVE") is not None:
        yc = makro["YIELD_CURVE"]
        status = "OK" if yc > 0 else "ODWROCONA!"
        tekst += f"Krzywa: {yc:+.2f} ({status})  "
    if makro.get("FEDFUNDS"):
        tekst += f"FED: {makro['FEDFUNDS']['value']}%\n"
    if makro.get("OIL_WTI"):
        tekst += f"Ropa: ${makro['OIL_WTI']['value']}\n"
    tekst += "────────────────────────────\n"
    tekst += "Nastepne: 07:00 | 12:30 | 18:30 | 20:30\n"
    tekst += "<i>COT is contextual, not predictive.</i>"

    return tekst


def buduj_daily_report_md(wyniki: list, makro: dict, tryb: str, health_status: str, payload: dict = None) -> str:
    """Pelny raport w formacie Markdown (do zalacznika daily_report.md)."""
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = f"# {AGENT_NAME} - Full Daily Report\n\n"
    md += f"**Tryb:** {tryb} | **Data:** {teraz}\n\n"
    md += f"## SYSTEM HEALTH: {health_status}\n\n"
    md += f"- Dataset: {len(wyniki) if wyniki else 0} instrumentow\n"
    md += f"- Warstwy: COT, Regime, Flow, Surprise, Sentiment, News\n\n"
    instr = (payload or {}).get("instrukcja") or {}
    if instr:
        md += "## INSTRUKCJA – CO ROBIĆ DZIŚ\n\n"
        md += f"**DECYZJA:** {instr.get('decision', 'WCHODŹ Z OGRANICZENIAMI')}\n\n"
        for r in instr.get("reasons", []):
            md += f"- {r}\n"
        top_ideas = instr.get("top_ideas", [])
        if top_ideas:
            md += "\n**Jeśli wchodzisz:**\n\n"
            for i, idea in enumerate(top_ideas[:3], 1):
                md += f"{i}. {idea.get('co','')} | {idea.get('suggested_size_desc','')}\n"
                md += f"   {idea.get('rationale','')}\n\n"
        if instr.get("ryzyka"):
            md += "**Ryzyka:** " + "; ".join(instr["ryzyka"]) + "\n\n"
    md += "## SCORING PER WALUTA\n\n"
    md += "| WALUTA | BIAS | SCORE | CONVICTION | REZIM | FLOW |\n"
    md += "|--------|------|-------|------------|-------|------|\n"
    for w in (wyniki or [])[:12]:
        md += f"| {w.get('instrument','')} | {w.get('bias','')} | {w.get('lacznie',0)}/100 | {w.get('conviction','')} | {w.get('typ_rezimu','')} | {w.get('flow_score',0)}/20 |\n"
    md += "\n## MAKRO\n\n"
    if makro.get("DXY"):
        md += f"- DXY: {makro['DXY']['value']}\n"
    if makro.get("US10Y"):
        md += f"- US10Y: {makro['US10Y']['value']}%\n"
    if makro.get("YIELD_CURVE") is not None:
        md += f"- Krzywa dochodowosci: {makro['YIELD_CURVE']:+.2f}\n"
    if makro.get("FEDFUNDS"):
        md += f"- FED: {makro['FEDFUNDS']['value']}%\n"
    if makro.get("OIL_WTI"):
        md += f"- Ropa WTI: ${makro['OIL_WTI']['value']}\n"
    md += "\n---\n*COT is contextual, not predictive. SofikaMax Agent.*\n"
    return md


def buduj_daily_report_md_z_payload(wyniki, makro, tryb, health_status, payload):
    """Pelny raport .md z komentarzem i weryfikacja (gdy payload podany)."""
    md = buduj_daily_report_md(wyniki, makro, tryb, health_status, payload)
    if not payload:
        return md
    comm = (payload.get("commentary") or "").strip()
    if comm:
        md += "\n\n## Komentarz analityka\n\n" + comm + "\n"
    verified = payload.get("verified") or []
    if verified:
        hit = sum(1 for v in verified[:10] if v.get("hit"))
        md += f"\n## Weryfikacja sygnalow\n\nOstatnie: {hit}/{min(10, len(verified))} trafionych.\n"
    return md


def wyslij_raport(wyniki: list, makro: dict, tryb: str, wyslij_plik_md: bool = True, payload: dict = None):
    """
    Wysyła raport jako PLIK PDF do pobrania (główna dostawa). Przy błędzie PDF – komunikat + raport tekstowy.
    """
    print(f"\nPrzygotowuje raport Telegram ({AGENT_NAME}, {tryb})...")
    health_status, _ = _system_health(wyniki)
    teraz = datetime.now()
    teraz_str = teraz.strftime("%d.%m.%Y %H:%M")
    godzina = teraz.hour
    if godzina < 10:
        pora = "Raport poranny"
    elif godzina < 15:
        pora = "Raport poludniowy"
    elif godzina < 20:
        pora = "Raport wieczorny"
    else:
        pora = "Raport nocny"

    instr = (payload or {}).get("instrukcja") or {}
    decision = instr.get("decision") or "WCHODŹ Z OGRANICZENIAMI"
    recipients = get_recipients()

    # 1) Najpierw generuj PDF – to jest główna dostawa (plik do pobrania)
    pdf_bytes = None
    try:
        from report_pdf import build_report_pdf
        pdf_bytes = build_report_pdf(wyniki, makro, payload or {})
    except Exception as e:
        print(f"   [PDF] Blad generowania: {e}")
        traceback.print_exc()
        _log_pdf_error(e)  # zapis do data/pdf_error.log – przy harmonogramie wiadomo, czemu tekst zamiast PDF
        wyslij_do_wszystkich(
            f"<b>{AGENT_NAME}</b>\nRaport PDF niedostepny: {str(e)[:150]}.\nWysylam raport w formacie tekstowym."
        )
        tekst = formatuj_raport_telegram(wyniki, makro, tryb, health_status, payload)
        wyslij_do_wszystkich(tekst)
        pdf_ok = False
    else:
        if not pdf_bytes or len(pdf_bytes) < 500:
            print(f"   [PDF] Odrzucono: rozmiar {len(pdf_bytes) if pdf_bytes else 0} bajtow.")
            wyslij_do_wszystkich(
                f"<b>{AGENT_NAME}</b>\nRaport PDF nie zostal wygenerowany (pusty plik). Wysylam raport tekstowy."
            )
            tekst = formatuj_raport_telegram(wyniki, makro, tryb, health_status, payload)
            wyslij_do_wszystkich(tekst)
            pdf_ok = False
        else:
            # 2) Wysylka PDF jako dokument (sendDocument) – kazdy odbiorca dostaje plik do pobrania
            nazwa_pdf = f"SofikaMax_Raport_{teraz.strftime('%Y%m%d_%H%M')}.pdf"
            caption_pdf = f"{AGENT_NAME} | {pora} | {teraz_str} – raport do pobrania (PDF)."
            pdf_ok = False
            for chat_id in recipients:
                if wyslij_dokument_bytes(chat_id, nazwa_pdf, pdf_bytes, caption_pdf, "application/pdf"):
                    print(f"   Wyslano PDF do {chat_id}")
                    pdf_ok = True
            if not pdf_ok:
                wyslij_do_wszystkich(
                    f"<b>{AGENT_NAME}</b>\nNie udalo sie wyslac pliku PDF. Raport tekstowy ponizej."
                )
                tekst = formatuj_raport_telegram(wyniki, makro, tryb, health_status, payload)
                wyslij_do_wszystkich(tekst)

    # 3) Gdy PDF dostarczony – jedna krotka wiadomosc (podsumowanie)
    if pdf_ok:
        short_msg = (
            f"<b>{AGENT_NAME}</b> | {pora} | {teraz_str}\n"
            f"Decyzja: <b>{decision}</b>. Pelny raport w zalaczniku PDF powyzej (plik do pobrania)."
        )
        wyslij_do_wszystkich(short_msg)

    if wyslij_plik_md:
        md_content = buduj_daily_report_md_z_payload(
            wyniki, makro, tryb, health_status, payload
        ) if payload else buduj_daily_report_md(wyniki, makro, tryb, health_status)
        nazwa = f"daily_report_{teraz.strftime('%Y%m%d_%H%M')}.md"
        caption = f"{AGENT_NAME} | Full Daily Report | {tryb}"
        for chat_id in get_recipients():
            if wyslij_dokument(chat_id, nazwa, md_content, caption):
                print(f"   Wyslano zalacznik .md do {chat_id}")

    # 4) Archiwum – zapis metadanych raportu (do dashboardu i porownan)
    try:
        from report_archive import save_report
        save_report(
            report_date=teraz.strftime("%Y-%m-%d"),
            report_time=teraz.strftime("%H:%M"),
            decision=decision,
            summary={
                "health": health_status,
                "signals": [
                    {
                        "instrument": w.get("instrument"),
                        "bias": w.get("meta_bias"),
                        "score": w.get("lacznie"),
                        "conviction": w.get("conviction"),
                    }
                    for w in (wyniki or [])[:5]
                ],
                "macro": {
                    "DXY": makro.get("DXY", {}).get("value") if isinstance(makro.get("DXY"), dict) else None,
                    "US10Y": makro.get("US10Y", {}).get("value") if isinstance(makro.get("US10Y"), dict) else None,
                    "FED": makro.get("FEDFUNDS", {}).get("value") if isinstance(makro.get("FEDFUNDS"), dict) else None,
                    "OIL": makro.get("OIL_WTI", {}).get("value") if isinstance(makro.get("OIL_WTI"), dict) else None,
                },
                "reasons": instr.get("reasons", [])[:3],
                "ryzyka": instr.get("ryzyka", [])[:3],
            },
        )
    except Exception as e:
        print(f"   Archiwum raportu (nie blokuje): {e}")

    # 5) Cache pelnego raportu – Dashboard moze go auto-zaladowac (te same godziny co Telegram)
    try:
        from report_cache import save_report_cache
        save_report_cache(wyniki, makro, payload or {})
    except Exception as e:
        print(f"   Cache raportu (nie blokuje): {e}")


def test_polaczenia():
    tekst  = f"<b>{AGENT_NAME} - Test</b>\n\n"
    tekst += "Bot dziala poprawnie.\n\n"
    tekst += "Raporty o:\n"
    tekst += "07:00 - Raport poranny\n"
    tekst += "12:30 - Raport poludniowy\n"
    tekst += "18:30 - Raport wieczorny\n"
    tekst += "20:30 - Raport nocny\n\n"
    tekst += f"Test: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    print("Wysylam test...")
    wyslij_do_wszystkich(tekst)


def dodaj_uzytkownika(chat_id: int, imie: str = ""):
    try:
        from subscription_store import add_subscriber
        ok, msg = add_subscriber(telegram_id=chat_id, name=imie or "")
        if ok:
            print(f"Dodano: {imie} ({chat_id})")
            wyslij_wiadomosc(
                chat_id,
                f"Witaj {imie or 'Subskrybencie'}!\nZostales dodany do {AGENT_NAME}.\nRaporty: 07:00 | 12:30 | 18:30 | 20:30"
            )
        else:
            print(msg)
    except Exception as e:
        print(f"Blad dodawania: {e}")


def usun_uzytkownika(chat_id: int):
    try:
        from subscription_store import remove_subscriber
        ok, msg = remove_subscriber(chat_id)
        print(msg if ok else msg)
    except Exception as e:
        print(f"Blad usuwania: {e}")


if __name__ == "__main__":
    print("\n" + "="*50)
    print(f"  {AGENT_NAME} - TELEGRAM BOT")
    print("="*50)
    rec = get_recipients()
    print(f"Odbiorcy raportow (subskrybenci): {len(rec)}")
    for uid in rec:
        print(f"  - {uid}")
    print("\nWysylam wiadomosc testowa...")
    test_polaczenia()
    print("\n" + "="*50)
