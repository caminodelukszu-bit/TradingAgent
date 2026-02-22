import requests
import pandas as pd
from datetime import datetime, timedelta

# ============================================================
# ZLACZA NA PRZYSZLOSC (zakomentowane - gotowe do podlaczenia)
# ============================================================
# BLOOMBERG_API_KEY = ""     # ~2000 USD/mc - enterprise
# REUTERS_API_KEY   = ""     # do uzgodnienia z Refinitiv
# ECONOMIST_API_KEY = ""     # dane makroekonomiczne premium
# ============================================================

# Bezplatne zrodlo - ForexFactory kalendarz
FOREXFACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Wagi waznosci wydarzen
IMPACT_WEIGHTS = {
    "high":   3,
    "medium": 1,
    "low":    0,
}

# Najwazniejsze wydarzenia per waluta
TOP_EVENTS = {
    "USD": ["Non-Farm Payrolls", "CPI", "FOMC", "GDP", "Retail Sales", "PCE"],
    "EUR": ["ECB Rate Decision", "CPI Flash", "GDP Flash", "PMI"],
    "GBP": ["BOE Rate Decision", "CPI", "GDP"],
    "JPY": ["BOJ Rate Decision", "CPI", "GDP"],
    "AUD": ["RBA Rate Decision", "CPI", "Employment"],
    "CAD": ["BOC Rate Decision", "CPI", "Employment"],
    "CHF": ["SNB Rate Decision", "CPI"],
    "NZD": ["RBNZ Rate Decision", "CPI", "GDP"],
}


def get_calendar() -> list:
    """
    Pobiera kalendarz ekonomiczny z ForexFactory.
    Przyszlosc: zamienic na Bloomberg/Reuters gdy bedzie budzet.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(FOREXFACTORY_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            print(f"   Pobrano {len(data)} wydarzen z ForexFactory")
            try:
                from history_archive import upsert_events
                events_for_archive = [
                    {
                        "date": e.get("date", ""),
                        "currency": (e.get("country", "") or e.get("currency", "USD"))[:3],
                        "event": e.get("title", e.get("event", "")),
                        "impact": (e.get("impact") or "medium").lower(),
                        "forecast": str(e.get("forecast", "")),
                        "previous": str(e.get("previous", "")),
                    }
                    for e in (data if isinstance(data, list) else [])
                    if e.get("date") or e.get("title")
                ]
                if events_for_archive:
                    upsert_events(events_for_archive)
            except Exception:
                pass
            return data
        else:
            print(f"   ForexFactory niedostepny (status {r.status_code})")
            return _get_manual_calendar()
    except Exception as e:
        print(f"   Blad kalendarza: {e}")
        return _get_manual_calendar()


def _get_manual_calendar() -> list:
    """
    Reczny kalendarz jako fallback gdy API niedostepne.
    Aktualizuj co tydzien lub podlacz platne API.
    """
    print("   Uzywam recznego kalendarza (fallback)")
    today = datetime.now()

    # Przykladowe wydarzenia - aktualizuj recznie
    events = [
        {
            "date":     (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            "time":     "14:30",
            "currency": "USD",
            "event":    "Non-Farm Payrolls",
            "impact":   "high",
            "forecast": "180K",
            "previous": "200K",
        },
        {
            "date":     (today + timedelta(days=5)).strftime("%Y-%m-%d"),
            "time":     "14:30",
            "currency": "USD",
            "event":    "CPI m/m",
            "impact":   "high",
            "forecast": "0.3%",
            "previous": "0.4%",
        },
        {
            "date":     (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "time":     "20:00",
            "currency": "USD",
            "event":    "FOMC Meeting Minutes",
            "impact":   "high",
            "forecast": "",
            "previous": "",
        },
    ]
    return events


def analyze_event_risk(currency: str = None, days_ahead: int = 7) -> dict:
    """
    Ocenia ryzyko eventowe dla waluty w nastepnych X dniach.
    Generuje penalty points dla systemu scoringu.
    """
    print(f"\n   Sprawdzam ryzyko eventowe: {currency or 'WSZYSTKIE'}")

    calendar = get_calendar()
    today    = datetime.now()
    deadline = today + timedelta(days=days_ahead)

    upcoming = []
    for event in calendar:
        try:
            # Parsuj date
            date_str = event.get("date", "")
            if not date_str:
                continue

            event_date = pd.to_datetime(date_str)
            if not (today <= event_date <= deadline):
                continue

            # Filtruj po walucie jesli podana
            event_currency = event.get("currency", "").upper()
            if currency and event_currency != currency.upper():
                continue

            # Tylko medium i high impact
            impact = event.get("impact", "low").lower()
            if impact == "low":
                continue

            upcoming.append({
                "date":     event_date.strftime("%Y-%m-%d"),
                "time":     event.get("time", ""),
                "currency": event_currency,
                "event":    event.get("event", event.get("title", "")),
                "impact":   impact,
                "forecast": event.get("forecast", ""),
                "previous": event.get("previous", ""),
                "days_to":  (event_date - today).days,
            })
        except:
            continue

    # Oblicz penalty
    penalty     = 0
    high_events = [e for e in upcoming if e["impact"] == "high"]
    med_events  = [e for e in upcoming if e["impact"] == "medium"]

    # Evento w ciagu 24h = duza kara
    critical = [e for e in high_events if e["days_to"] <= 1]
    if critical:
        penalty -= 20
    elif high_events:
        penalty -= 10
    if med_events:
        penalty -= 5

    # Risk level
    if penalty <= -20:
        risk_level = "KRYTYCZNY"
    elif penalty <= -10:
        risk_level = "WYSOKI"
    elif penalty <= -5:
        risk_level = "SREDNI"
    else:
        risk_level = "NISKI"

    # Wyswietl nadchodzace
    if upcoming:
        print(f"   Nadchodzace wydarzenia ({currency or 'wszystkie'}):")
        for e in upcoming[:5]:
            print(f"   [{e['impact'].upper()}] {e['date']} {e['time']} - {e['currency']} {e['event']}")
    else:
        print(f"   Brak waznych wydarzen w ciagu {days_ahead} dni")

    return {
        "currency":     currency or "ALL",
        "penalty":      penalty,
        "risk_level":   risk_level,
        "events_count": len(upcoming),
        "high_count":   len(high_events),
        "critical":     len(critical),
        "upcoming":     upcoming[:10],
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_upcoming_events_summary(currency: str = None, days_ahead: int = 7, max_events: int = 5) -> str:
    """Krótki tekst nadchodzących wydarzeń (do zapisu przy sygnale). Bez print()."""
    try:
        calendar = get_calendar()
    except Exception:
        return ""
    today = datetime.now()
    deadline = today + timedelta(days=days_ahead)
    names = []
    for event in calendar:
        try:
            date_str = event.get("date", "")
            if not date_str:
                continue
            event_date = pd.to_datetime(date_str)
            if not (today <= event_date <= deadline):
                continue
            event_currency = event.get("currency", "").upper()
            if currency and event_currency != currency.upper():
                continue
            impact = event.get("impact", "low").lower()
            if impact == "low":
                continue
            name = event.get("event", event.get("title", ""))[:40]
            if name and name not in names:
                names.append(name)
            if len(names) >= max_events:
                break
        except Exception:
            continue
    return ", ".join(names) if names else ""


def get_event_summary() -> dict:
    """
    Podsumowanie ryzyka eventowego dla wszystkich walut.
    Wywolywane codziennie o 7:00 razem z raportem.
    """
    waluty = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF"]
    wyniki = {}

    for w in waluty:
        wyniki[w] = analyze_event_risk(currency=w, days_ahead=7)

    return wyniki


if __name__ == "__main__":
    print("\n" + "="*60)
    print(f"{'KALENDARZ EKONOMICZNY':^60}")
    print(f"{'Ryzyko eventowe na nastepne 7 dni':^60}")
    print("="*60)

    wyniki = get_event_summary()

    print(f"\n{'WALUTA':<8} {'RYZYKO':<12} {'PENALTY':<10} {'WYSOKIE':<10} {'KRYTYCZNE'}")
    print("-"*55)
    for w, r in wyniki.items():
        print(
            f"{w:<8} "
            f"{r['risk_level']:<12} "
            f"{r['penalty']:<10} "
            f"{r['high_count']:<10} "
            f"{r['critical']}"
        )
    print("="*60)
    print("\nLegenda:")
    print("  KRYTYCZNY = wydarzenie w ciagu 24h (-20 pkt)")
    print("  WYSOKI    = wydarzenie high impact w tygodniu (-10 pkt)")
    print("  SREDNI    = wydarzenie medium impact (-5 pkt)")
    print("  NISKI     = brak waznych wydarzen (0 pkt)")