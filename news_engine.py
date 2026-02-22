import requests
from datetime import datetime

# ============================================================
# KONFIGURACJA
# ============================================================
NEWSAPI_KEY = "063da965baf84687940539b91daf8dff"

# Preferowane zrodla (Reuters, AP, BBC, Guardian, NYT, WSJ...) – sortowanie na gore listy
try:
    from config import NEWS_PREFERRED_SOURCES
except ImportError:
    NEWS_PREFERRED_SOURCES = [
        "Reuters", "Associated Press", "AFP", "BBC News", "The Guardian",
        "The New York Times", "Wall Street Journal", "The Economist",
    ]

# Przyszle klucze premium (zostawione na pozniej)
# BLOOMBERG_KEY  = ""  # ~2000 USD/mc - enterprise
# REUTERS_KEY    = ""  # Refinitiv
# ECONOMIST_KEY  = ""  # The Economist

BASE_URL = "https://newsapi.org/v2/everything"
# ============================================================

# Slowa kluczowe per waluta/instrument
KEYWORDS = {
    "USD": ["Federal Reserve", "Fed rate", "dollar", "FOMC", "Powell", "US economy", "inflation USA"],
    "EUR": ["ECB", "euro zone", "European Central Bank", "Lagarde", "eurozone GDP"],
    "GBP": ["Bank of England", "British pound", "BOE", "UK economy", "sterling"],
    "JPY": ["Bank of Japan", "BOJ", "yen", "Japan economy", "Ueda"],
    "AUD": ["RBA", "Reserve Bank Australia", "Australian dollar", "AUD"],
    "CAD": ["Bank of Canada", "BOC", "Canadian dollar", "CAD oil"],
    "CHF": ["Swiss franc", "SNB", "Swiss National Bank"],
    "NZD": ["RBNZ", "New Zealand dollar", "Reserve Bank New Zealand"],
    "GOLD": ["gold price", "gold rally", "safe haven gold", "XAU"],
    "SILVER": ["silver price", "XAG", "silver rally"],
    "OIL": ["crude oil", "WTI", "OPEC", "oil price", "Brent"],
}

# Slowa pozytywne - zwykla waga +0.15
SLOWA_POZYTYWNE = [
    "rally", "surge", "gain", "rise", "strong", "bullish", "growth",
    "positive", "increase", "higher", "boost", "optimism", "recovery",
    "beat", "better", "improve", "upgrade", "hawkish", "record",
    "ceasefire", "peace", "deal", "agreement", "stimulus", "rebound",
]

# Slowa negatywne - zwykla waga -0.15
SLOWA_NEGATYWNE = [
    "fall", "drop", "decline", "weak", "bearish", "recession", "risk",
    "negative", "decrease", "lower", "concern", "fear", "miss",
    "worse", "downgrade", "dovish", "crisis", "warning", "slowdown",
    # Geopolityka
    "war", "attack", "military", "strike", "conflict", "sanctions",
    "invasion", "troops", "missile", "nuclear", "iran", "collapse",
    "aircraft carrier", "escalation", "threat", "retaliation",
    "blockade", "embargo", "explosion", "shutdown", "default",
]

# Slowa krytyczne - podwojna waga -0.30
# Uzywane gdy sytuacja geopolityczna jest powazna
SLOWA_KRYTYCZNE = [
    "world war", "nuclear strike", "nuclear war", "invasion",
    "attack iran", "iran attack", "military strike", "aircraft carrier",
    "oil embargo", "sanctions russia", "war escalation",
    "missile attack", "bomb", "warships", "fighter jets",
    "troops deployed", "emergency", "catastrophe",
]
# Konteksty wykluczajace "emergency" (np. sport: referee reform)
EMERGENCY_FALSE_POSITIVE = [
    "referee", "figc", "serie a", "football", "soccer", "sport", "reform",
]

# Slowa pozytywne krytyczne - podwojna waga +0.30
SLOWA_POZYTYWNE_KRYTYCZNE = [
    "ceasefire agreement", "peace deal", "war ends",
    "sanctions lifted", "historic deal", "major stimulus",
]


def pobierz_newsy(instrument: str, limit: int = 10) -> list:
    """
    Pobiera najnowsze newsy dla instrumentu z NewsAPI.
    Przyszlosc: zastapic Bloomberg/Reuters premium.
    """
    keywords = KEYWORDS.get(instrument.upper(), [instrument])
    query    = " OR ".join(keywords[:3])

    params = {
        "q":        query,
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": limit,
        "apiKey":   NEWSAPI_KEY,
    }

    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        if r.status_code == 200:
            data     = r.json()
            artykuly = data.get("articles", [])
            # Preferowane zrodla (Reuters, AP, BBC...) na gore – rzetelne agencje pierwsze
            preferred = [s.lower() for s in (NEWS_PREFERRED_SOURCES or [])]
            def _source_rank(a):
                name = (a.get("source") or {}).get("name") or ""
                for i, p in enumerate(preferred):
                    if p in name.lower():
                        return i
                return len(preferred)
            artykuly.sort(key=_source_rank)
            print(f"   Pobrano {len(artykuly)} newsow dla {instrument}")
            return artykuly
        elif r.status_code == 426:
            print(f"   NewsAPI: plan Developer - tylko lokalne testy")
            return []
        else:
            print(f"   NewsAPI blad {r.status_code} dla {instrument}")
            return []
    except Exception as e:
        print(f"   Blad NewsAPI: {e}")
        return []


def analizuj_sentyment(tekst: str) -> float:
    """
    Analiza sentymentu na podstawie slow kluczowych.
    Uwzglednia geopolityke z podwojna waga.
    Zwraca wartosc od -1.0 do +1.0
    """
    if not tekst:
        return 0.0

    tekst_lower = tekst.lower()
    wynik       = 0.0

    # Zwykle slowa pozytywne
    for slowo in SLOWA_POZYTYWNE:
        if slowo in tekst_lower:
            wynik += 0.15

    # Zwykle slowa negatywne
    for slowo in SLOWA_NEGATYWNE:
        if slowo in tekst_lower:
            wynik -= 0.15

    # Krytyczne slowa negatywne - podwojna waga
    for slowo in SLOWA_KRYTYCZNE:
        if slowo not in tekst_lower:
            continue
        if slowo == "emergency" and any(f in tekst_lower for f in EMERGENCY_FALSE_POSITIVE):
            continue  # np. "emergency referee reform" - sport, nie geopolityka
        wynik -= 0.30
        print(f"   GEOPOLITYKA KRYTYCZNA: '{slowo}' wykryte!")

    # Krytyczne slowa pozytywne - podwojna waga
    for slowo in SLOWA_POZYTYWNE_KRYTYCZNE:
        if slowo in tekst_lower:
            wynik += 0.30

    return max(-1.0, min(1.0, round(wynik, 2)))


def wykryj_geopolityke(artykuly: list) -> dict:
    """
    Sprawdza czy w newsach sa krytyczne wydarzenia geopolityczne.
    Jesli tak - generuje ostrzezenie do raportu.
    """
    alert        = False
    alert_tekst  = ""
    ryzyko       = "NISKIE"

    for art in artykuly:
        tytul = (art.get("title", "") or "").lower()
        opis  = (art.get("description", "") or "").lower()
        tekst = f"{tytul} {opis}"

        for slowo in SLOWA_KRYTYCZNE:
            if slowo not in tekst:
                continue
            if slowo == "emergency" and any(f in tekst for f in EMERGENCY_FALSE_POSITIVE):
                continue  # sport / referee - nie geopolityka
            alert       = True
            ryzyko      = "KRYTYCZNE"
            alert_tekst = art.get("title", "")[:80]
            break

        if alert:
            break

    return {
        "alert":       alert,
        "ryzyko":      ryzyko,
        "alert_tekst": alert_tekst,
    }


def oblicz_nps(artykuly: list) -> dict:
    """
    Oblicza Narrative Power Score (NPS).
    Inspirowane systemem NIL v1.0 - mierzy sile narracji rynkowej.
    """
    if not artykuly:
        return {
            "nps":         0.0,
            "kierunek":    "NEUTRALNY",
            "sila":        "SLABA",
            "top_news":    "",
            "liczba":      0,
            "geopolityka": {"alert": False, "ryzyko": "NISKIE", "alert_tekst": ""},
        }

    wyniki_sentymentu = []
    top_news          = ""

    for art in artykuly:
        tytul = art.get("title", "") or ""
        opis  = art.get("description", "") or ""
        tekst = f"{tytul} {opis}"

        sentyment = analizuj_sentyment(tekst)
        wyniki_sentymentu.append(sentyment)

        if not top_news and tytul:
            top_news = tytul[:80]

    if not wyniki_sentymentu:
        return {
            "nps": 0.0, "kierunek": "NEUTRALNY", "sila": "SLABA",
            "top_news": "", "liczba": 0,
            "geopolityka": {"alert": False, "ryzyko": "NISKIE", "alert_tekst": ""},
        }

    # NPS - srednia wazona (nowsze newsy wazniejsze)
    n    = len(wyniki_sentymentu)
    wagi = [1 + (i / n) for i in range(n)]
    nps  = sum(s * w for s, w in zip(wyniki_sentymentu, wagi)) / sum(wagi)
    nps  = round(nps, 2)

    # Kierunek narracji
    if nps > 0.15:
        kierunek = "POZYTYWNY"
    elif nps < -0.15:
        kierunek = "NEGATYWNY"
    else:
        kierunek = "NEUTRALNY"

    # Sila narracji
    if abs(nps) > 0.5:
        sila = "SILNA"
    elif abs(nps) > 0.25:
        sila = "UMIARKOWANA"
    else:
        sila = "SLABA"

    # Sprawdz geopolityke
    geopolityka = wykryj_geopolityke(artykuly)

    return {
        "nps":         nps,
        "kierunek":    kierunek,
        "sila":        sila,
        "top_news":    top_news,
        "liczba":      len(artykuly),
        "geopolityka": geopolityka,
    }


def analyze_news(instrument: str) -> dict:
    """
    Glowna funkcja - analizuje newsy i sentyment dla instrumentu.
    Zwraca wynik gotowy do integracji z main.py
    """
    print(f"\n   Analizuje newsy: {instrument}")

    artykuly = pobierz_newsy(instrument)
    nps_data = oblicz_nps(artykuly)

    # Ostrzezenie geopolityczne
    geo = nps_data["geopolityka"]
    if geo["alert"]:
        print(f"   ALERT GEOPOLITYCZNY: {geo['alert_tekst']}")
        print(f"   Ryzyko: {geo['ryzyko']} - rozważ dodatkowa ostroznosc!")

    # Score (0-20)
    score = 0

    if nps_data["kierunek"] == "POZYTYWNY":
        score += 10
    elif nps_data["kierunek"] == "NEUTRALNY":
        score += 5

    if nps_data["sila"] == "SILNA":
        score += 10
    elif nps_data["sila"] == "UMIARKOWANA":
        score += 5

    # Kara za krytyczne ryzyko geopolityczne
    if geo["ryzyko"] == "KRYTYCZNE":
        score = max(0, score - 10)
        print(f"   Kara geopolityczna: -10 pkt")

    # Bias z newsow
    if nps_data["kierunek"] == "POZYTYWNY" and nps_data["sila"] != "SLABA":
        bias = "POZYTYWNY"
    elif nps_data["kierunek"] == "NEGATYWNY" and nps_data["sila"] != "SLABA":
        bias = "NEGATYWNY"
    else:
        bias = "NEUTRALNY"

    # Archiwum historii (dla AI)
    try:
        from history_archive import upsert_news_daily
        from datetime import datetime
        upsert_news_daily(
            instrument,
            datetime.now().strftime("%Y-%m-%d"),
            nps_data["nps"],
            nps_data["liczba"],
            bias,
            nps_data.get("top_news", ""),
        )
    except Exception:
        pass

    return {
        "instrument":  instrument,
        "nps":         nps_data["nps"],
        "kierunek":    nps_data["kierunek"],
        "sila":        nps_data["sila"],
        "bias":        bias,
        "top_news":    nps_data["top_news"],
        "liczba":      nps_data["liczba"],
        "geopolityka": geo["ryzyko"],
        "geo_alert":   geo["alert"],
        "geo_tekst":   geo["alert_tekst"],
        "score":       min(20, score),
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def analyze_news_all() -> dict:
    """
    Analizuje newsy dla wszystkich instrumentow.
    Wywolywane przez main.py
    """
    instrumenty = ["USD", "EUR", "GBP", "JPY", "GOLD", "OIL"]
    wyniki      = {}
    for instr in instrumenty:
        wyniki[instr] = analyze_news(instr)
    return wyniki


if __name__ == "__main__":
    print("\n" + "="*65)
    print(f"{'NEWS ENGINE - SENTYMENT RYNKOWY':^65}")
    print(f"{'NewsAPI.org (Reuters, BBC, FT)':^65}")
    print(f"{'Z detekcja ryzyka geopolitycznego':^65}")
    print("="*65)

    instrumenty = ["USD", "EUR", "GBP", "JPY", "GOLD", "OIL"]

    wyniki = []
    for instr in instrumenty:
        r = analyze_news(instr)
        wyniki.append(r)

    print(f"\n{'='*65}")
    print(f"{'WYNIKI SENTYMENTU':^65}")
    print(f"{'='*65}")
    print(f"{'INSTR':<8} {'NPS':<8} {'KIERUNEK':<14} {'SILA':<12} {'GEOPOLITYKA'}")
    print(f"{'-'*65}")

    for r in wyniki:
        geo_ikona = "ALERT!" if r["geo_alert"] else "OK"
        print(
            f"{r['instrument']:<8} "
            f"{r['nps']:+.2f}{'':4}"
            f"{r['kierunek']:<14} "
            f"{r['sila']:<12} "
            f"{geo_ikona}"
        )
        if r["top_news"]:
            print(f"  News: {r['top_news']}")
        if r["geo_alert"]:
            print(f"  GEOPOLITYKA: {r['geo_tekst']}")

    print("="*65)
    print("\nWAZNE: System wykrywa geopolityke ale nie zastapi")
    print("Twojej wlasnej oceny sytuacji na swiecie!")
    print("Przy powaznych wydarzeniach - decyduj samodzielnie.")