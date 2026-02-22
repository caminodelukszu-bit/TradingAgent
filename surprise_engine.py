import requests
import pandas as pd
from datetime import datetime
from config import FRED_API_KEY

# Wskazniki makro per waluta
CURRENCY_INDICATORS = {
    "USD": {
        "CPI":    "CPIAUCSL",
        "NFP":    "PAYEMS",
        "GDP":    "GDP",
        "RETAIL": "RSAFS",
    },
    "EUR": {
        "CPI":    "CP0000EZ19M086NEST",
        "GDP":    "EURGDPNQDSMEI",
    },
    "GBP": {
        "CPI":    "GBRCPIALLMINMEI",
    },
    "JPY": {
        "CPI":    "JPNCPIALLMINMEI",
    },
    "AUD": {
        "CPI":    "AUSCPIALLQINMEI",
    },
    "CAD": {
        "CPI":    "CPALCY01CAM661N",
    },
}

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_series(series_id: str, limit: int = 24, use_archive_first: bool = True) -> pd.DataFrame:
    """FRED: najpierw archiwum (history_archive), potem API + zapis."""
    if use_archive_first:
        try:
            from history_archive import get_history_fred, upsert_fred
            df = get_history_fred(series_id, limit=min(limit, 200))
            if df is not None and len(df) >= 4:
                return df
        except ImportError:
            pass
    url = (
        f"{BASE_URL}?series_id={series_id}"
        f"&api_key={FRED_API_KEY}"
        f"&file_type=json&limit={limit}&sort_order=desc"
    )
    try:
        r = requests.get(url, timeout=15)
        data = r.json().get("observations", [])
        if not data:
            return None
        df = pd.DataFrame(data)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"]  = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
        if use_archive_first:
            try:
                from history_archive import upsert_fred
                upsert_fred(series_id, df)
            except Exception:
                pass
        return df
    except Exception:
        return None


def calculate_surprise_zscore(df: pd.DataFrame, window: int = 12) -> dict:
    """
    Oblicza Z-score zaskoczeń.
    Jak bardzo ostatnia zmiana odbiega od historycznej normy?
    """
    if df is None or len(df) < 4:
        return {"zscore": 0, "surprise": 0, "momentum": "NIEZNANY"}

    df["change"] = df["value"].diff()
    df = df.dropna(subset=["change"])

    if len(df) < 3:
        return {"zscore": 0, "surprise": 0, "momentum": "NIEZNANY"}

    latest_change = df["change"].iloc[-1]
    mean_change   = df["change"].tail(window).mean()
    std_change    = df["change"].tail(window).std()

    zscore = (latest_change - mean_change) / std_change if std_change != 0 else 0

    last_3 = df["change"].tail(3).values
    pos = sum(1 for c in last_3 if c > 0)
    neg = sum(1 for c in last_3 if c < 0)

    if pos >= 2:
        momentum = "POPRAWIA SIE"
    elif neg >= 2:
        momentum = "POGARSZA SIE"
    else:
        momentum = "STABILNY"

    return {
        "zscore":   round(zscore, 2),
        "surprise": round(latest_change, 4),
        "momentum": momentum
    }


def analyze_surprise(currency: str) -> dict:
    """
    Glowna funkcja - oblicza Surprise Intelligence dla waluty.
    Inspirowane modulem M3 z systemu NIL v1.0
    """
    print(f"\n   Analizuje zaskoczenia makro: {currency}")

    indicators = CURRENCY_INDICATORS.get(currency.upper())
    if not indicators:
        return _empty(currency)

    zscores   = []
    momentums = []
    details   = {}

    for name, series_id in indicators.items():
        df     = get_fred_series(series_id)
        result = calculate_surprise_zscore(df)
        zscores.append(result["zscore"])
        momentums.append(result["momentum"])
        details[name] = result
        print(f"   {name}: Z={result['zscore']:+.2f} | {result['momentum']}")

    if not zscores:
        return _empty(currency)

    # Sredni Z-score zaskoczeń (ostatnie 4 tygodnie)
    surprise_4w = round(sum(zscores) / len(zscores), 2)

    # Ogolny momentum
    pop  = sum(1 for m in momentums if m == "POPRAWIA SIE")
    pog  = sum(1 for m in momentums if m == "POGARSZA SIE")

    if pop > pog:
        overall_momentum = "POPRAWIA SIE"
    elif pog > pop:
        overall_momentum = "POGARSZA SIE"
    else:
        overall_momentum = "STABILNY"

    # Coupling - jak mocno cena reaguje na dane
    coupling = min(100, int(abs(surprise_4w) * 20))

    # Jakosc danych
    n = len(indicators)
    if n >= 4:
        health = "WYSOKA PEWNOSC"
    elif n >= 2:
        health = "SREDNIA"
    else:
        health = "NIEWYSTARCZAJACA"

    # Score (0-20)
    score = 0
    if overall_momentum == "POPRAWIA SIE":
        score += 10
    elif overall_momentum == "STABILNY":
        score += 5

    if abs(surprise_4w) > 1.5:
        score += 10
    elif abs(surprise_4w) > 0.5:
        score += 5

    # Kierunek z zaskoczeń
    if surprise_4w > 0.5 and overall_momentum == "POPRAWIA SIE":
        bias = "POZYTYWNY"
    elif surprise_4w < -0.5 and overall_momentum == "POGARSZA SIE":
        bias = "NEGATYWNY"
    else:
        bias = "NEUTRALNY"

    return {
        "currency":    currency,
        "surprise_4w": surprise_4w,
        "momentum":    overall_momentum,
        "coupling":    coupling,
        "health":      health,
        "bias":        bias,
        "score":       min(20, score),
        "details":     details,
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M")
    }


def _empty(currency: str) -> dict:
    return {
        "currency":    currency,
        "surprise_4w": 0,
        "momentum":    "NIEZNANY",
        "coupling":    0,
        "health":      "NIEWYSTARCZAJACA",
        "bias":        "NEUTRALNY",
        "score":       0,
        "details":     {},
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M")
    }


if __name__ == "__main__":
    waluty = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"]

    wyniki = []
    for cur in waluty:
        r = analyze_surprise(cur)
        wyniki.append(r)

    print(f"\n{'='*70}")
    print(f"{'SURPRISE INTELLIGENCE - M3':^70}")
    print(f"{'='*70}")
    print(f"{'WALUTA':<8} {'ZASKOCZENIE':<13} {'MOMENTUM':<18} {'COUPLING':<10} {'KIERUNEK'}")
    print(f"{'-'*70}")

    for r in wyniki:
        print(
            f"{r['currency']:<8} "
            f"{r['surprise_4w']:+.2f}{'':9}"
            f"{r['momentum']:<18} "
            f"{r['coupling']}%{'':6}"
            f"{r['bias']}"
        )

    print(f"{'='*70}")