# =============================================================================
# sentiment_engine.py - Layer 4: Retail Sentiment (kontrarianski)
# Zrodlo: MyFXBook API get-community-outlook.json
# Logika: Retail 80%+ LONG => instytucje czesto SHORT => sygnal SELL
#         Retail 80%+ SHORT => sygnal BUY
# Limit: 100 zapytan/24h (darmowy). Jedno wywolanie pobiera wszystkie pary.
# =============================================================================

import requests
from datetime import datetime

try:
    from config import MYFXBOOK_EMAIL, MYFXBOOK_PASSWORD
except ImportError:
    MYFXBOOK_EMAIL = ""
    MYFXBOOK_PASSWORD = ""

BASE_LOGIN = "https://www.myfxbook.com/api/login.json"
BASE_OUTLOOK = "https://www.myfxbook.com/api/get-community-outlook.json"

# Mapowanie symboli MyFXBook na nasze instrumenty.
# Dla XXXUSD: longPercentage = retail long XXX (waluta bazowa).
# Dla USDXXX: longPercentage = retail long USD, czyli short XXX = shortPercentage.
SENTIMENT_MAP = {
    "EURUSD": {"instrument": "EUR", "retail_long_key": "longPercentage"},
    "GBPUSD": {"instrument": "GBP", "retail_long_key": "longPercentage"},
    "AUDUSD": {"instrument": "AUD", "retail_long_key": "longPercentage"},
    "USDJPY": {"instrument": "JPY", "retail_long_key": "shortPercentage"},
    "USDCAD": {"instrument": "CAD", "retail_long_key": "shortPercentage"},
    "USDCHF": {"instrument": "CHF", "retail_long_key": "shortPercentage"},
    "XAUUSD": {"instrument": "GOLD", "retail_long_key": "longPercentage"},
    "GOLD":   {"instrument": "GOLD", "retail_long_key": "longPercentage"},
    "XAGUSD": {"instrument": "SILVER", "retail_long_key": "longPercentage"},
    "SILVER": {"instrument": "SILVER", "retail_long_key": "longPercentage"},
}

# Progi kontrarianskie (z briefingu)
PROG_LONG_EXTREME  = 80   # powyzej = retail bardzo long => sygnal SELL
PROG_SHORT_EXTREME = 20   # ponizej = retail bardzo short => sygnal BUY
CAPITULATION_PCT   = 20   # zmiana > 20% w 1 tyg = kapitulacja (wymaga cache)


def _get_session():
    """Logowanie do MyFXBook. Zwraca session ID lub None."""
    if not MYFXBOOK_EMAIL or not MYFXBOOK_PASSWORD:
        return None
    try:
        r = requests.get(
            BASE_LOGIN,
            params={"email": MYFXBOOK_EMAIL, "password": MYFXBOOK_PASSWORD},
            timeout=10
        )
        data = r.json()
        if data.get("error") is False and data.get("session"):
            return data["session"]
    except Exception as e:
        print(f"   [SENTIMENT] Blad logowania MyFXBook: {e}")
    return None


def _fetch_outlook(session):
    """Pobiera community outlook. Zwraca slownik symbol -> dane lub None."""
    if not session:
        return None
    try:
        r = requests.get(BASE_OUTLOOK, params={"session": session}, timeout=10)
        data = r.json()
        if data.get("error") is False and data.get("symbols"):
            return {s["name"].upper(): s for s in data["symbols"]}
    except Exception as e:
        print(f"   [SENTIMENT] Blad pobierania outlook: {e}")
    return None


def _retail_long_pct(symbol_data, key):
    """Wyciaga procent long (retail) dla waluty. key = longPercentage lub shortPercentage."""
    if not symbol_data:
        return None
    val = symbol_data.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _contrarian_score_and_bias(retail_long_pct):
    """
    Kontrarianski score 0-20 i bias.
    retail_long_pct = ile % retail jest long na walute.
    80%+ long => SELL (instytucje przeciw) => score wysoki dla sygnalu SELL.
    20%- long => BUY => score wysoki dla sygnalu BUY.
    20-80% => NEUTRAL, score 0.
    """
    if retail_long_pct is None:
        return 0, "NEUTRALNY"
    pct = max(0, min(100, retail_long_pct))
    # Sila kontrarianizmu: jak daleko od 50%
    distance = abs(pct - 50)
    if distance < 30:
        return 0, "NEUTRALNY"
    # Score 0-20 liniowo od 30 do 50 (distance)
    score = round((distance - 30) / 20 * 20)
    score = max(0, min(20, score))
    if pct >= PROG_LONG_EXTREME:
        bias = "SELL"
    elif pct <= PROG_SHORT_EXTREME:
        bias = "BUY"
    else:
        bias = "NEUTRALNY"
    return score, bias


def get_outlook_cache():
    """
    Jednorazowe pobranie outlook dla wszystkich symboli.
    Zwraca slownik: instrument -> {"poziom_retail_long": float, "shortPercentage": x, "longPercentage": y, ...}
    """
    session = _get_session()
    raw = _fetch_outlook(session)
    if not raw:
        return {}

    cache = {}
    for mf_symbol, config in SENTIMENT_MAP.items():
        instrument = config["instrument"]
        key = config["retail_long_key"]
        # MyFXBook moze zwracac EURUSD lub eurusd
        data = raw.get(mf_symbol) or raw.get(mf_symbol.lower())
        if not data:
            continue
        pct = _retail_long_pct(data, key)
        if pct is None:
            continue
        cache[instrument] = {
            "poziom_retail_long": round(pct, 1),
            "longPercentage": data.get("longPercentage"),
            "shortPercentage": data.get("shortPercentage"),
            "longPositions": data.get("longPositions"),
            "shortPositions": data.get("shortPositions"),
            "totalPositions": data.get("totalPositions"),
        }
    return cache


def analyze_sentiment(instrument: str, outlook_cache: dict = None) -> dict:
    """
    Glowna funkcja - Layer 4 Retail Sentiment dla jednego instrumentu.
    Zwraca slownik z kluczem score (0-20), bias (BUY/SELL/NEUTRALNY), poziom_retail_long, capitulation_alert.
    Gdy brak danych MyFXBook i wlaczony CLAUDE_SENTIMENT_FALLBACK: sentyment z Claude (na podstawie naglowkow).
    """
    instrument = instrument.upper()
    if outlook_cache is None:
        outlook_cache = get_outlook_cache()

    data = outlook_cache.get(instrument)
    if not data:
        # Fallback: Claude na podstawie naglowkow newsow
        try:
            from config import CLAUDE_SENTIMENT_FALLBACK
            if CLAUDE_SENTIMENT_FALLBACK:
                from claude_sentiment import get_claude_sentiment
                result = get_claude_sentiment(instrument)
                if result.get("source") == "claude" and result.get("rationale"):
                    if result.get("score", 0) > 0 or result.get("bias") != "NEUTRALNY":
                        return result
        except ImportError:
            pass
        except Exception:
            pass
        return _empty_sentiment(instrument)

    pct = data.get("poziom_retail_long")
    score, bias = _contrarian_score_and_bias(pct)

    # Kapitulacja: wymaga historii (cache z poprzedniego tygodnia). Na razie brak.
    capitulation_alert = False

    return {
        "instrument":          instrument,
        "score":              score,
        "bias":               bias,
        "poziom_retail_long": pct,
        "capitulation_alert": capitulation_alert,
        "long_positions":     data.get("longPositions"),
        "short_positions":    data.get("shortPositions"),
        "total_positions":    data.get("totalPositions"),
        "timestamp":          datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _empty_sentiment(instrument: str) -> dict:
    return {
        "instrument":          instrument,
        "score":              0,
        "bias":               "NEUTRALNY",
        "poziom_retail_long": None,
        "capitulation_alert":  False,
        "long_positions":     None,
        "short_positions":    None,
        "total_positions":    None,
        "timestamp":          datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_sentiment_all(instruments: list) -> dict:
    """
    Pobiera sentiment dla wszystkich instrumentow jednym wywolaniem API (1 request).
    Zwraca slownik instrument -> wynik analyze_sentiment().
    """
    cache = get_outlook_cache()
    return {inst: analyze_sentiment(inst, outlook_cache=cache) for inst in instruments}


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("SENTIMENT ENGINE - Layer 4 (Retail Kontrarianski)")
    print("=" * 60)
    if not MYFXBOOK_EMAIL or not MYFXBOOK_PASSWORD:
        print("Brak MYFXBOOK_EMAIL/MYFXBOOK_PASSWORD w config.py - ustaw aby testowac API.")
        print("Symulacja: zwracam neutral dla wszystkich.")
    instruments = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "GOLD", "SILVER"]
    results = fetch_sentiment_all(instruments)
    print(f"\n{'WALUTA':<8} {'RETAIL LONG %':<14} {'BIAS':<10} {'SCORE':<6} {'KAPITULACJA'}")
    print("-" * 60)
    for inst in instruments:
        r = results[inst]
        pct = r["poziom_retail_long"] if r["poziom_retail_long"] is not None else "N/A"
        print(f"{inst:<8} {str(pct):<14} {r['bias']:<10} {r['score']}/20   {r['capitulation_alert']}")
    print("=" * 60)
