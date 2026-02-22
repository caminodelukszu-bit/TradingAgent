import requests
import pandas as pd
from datetime import datetime
from config import FRED_API_KEY

FRED_SERIES = {
    "DXY":        "DTWEXBGS",
    "US10Y":      "DGS10",
    "US2Y":       "DGS2",
    "FEDFUNDS":   "FEDFUNDS",
    "CPI":        "CPIAUCSL",
    "UNRATE":     "UNRATE",
    "GDP":        "GDP",
    "OIL_WTI":   "DCOILWTICO",
}

BASE = "https://api.stlouisfed.org/fred/series/observations"

def get_fred(series_id: str, limit: int = 52, use_archive_first: bool = True) -> pd.DataFrame:
    """Pobiera dane FRED. Najpierw z archiwum (history_archive), potem API + zapis do archiwum."""
    if use_archive_first:
        try:
            from history_archive import get_history_fred, upsert_fred
            df = get_history_fred(series_id, limit=min(limit, 500))
            if df is not None and len(df) >= 5:
                return df
        except ImportError:
            pass
    url = (
        f"{BASE}?series_id={series_id}"
        f"&api_key={FRED_API_KEY}"
        f"&file_type=json"
        f"&limit={limit}"
        f"&sort_order=desc"
    )
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        obs  = data.get("observations", [])
        if not obs:
            return None
        df = pd.DataFrame(obs)
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
    except Exception as e:
        print(f"[X] FRED {series_id}: {e}")
        return None

def analyze_macro() -> dict:
    print("\n[MACRO] Pobieram dane makro z FRED...")
    results = {}
    score   = 0

    for name, sid in FRED_SERIES.items():
        df = get_fred(sid, use_archive_first=True)
        if df is None or len(df) < 5:
            print(f"   [X] {name}: brak danych")
            results[name] = None
            continue

        latest   = df["value"].iloc[-1]
        prev     = df["value"].iloc[-2]
        change   = latest - prev
        pct      = (change / prev * 100) if prev != 0 else 0

        results[name] = {
            "value":   round(latest, 2),
            "change":  round(change, 2),
            "pct":     round(pct, 2),
            "trend":   "UP" if change > 0 else "DOWN"
        }
        print(f"   [OK] {name}: {latest:.2f} ({pct:+.2f}%)")

    # Yield curve (10Y - 2Y)
    if results.get("US10Y") and results.get("US2Y"):
        spread = results["US10Y"]["value"] - results["US2Y"]["value"]
        results["YIELD_CURVE"] = round(spread, 2)
        print(f"   [*] Yield Curve (10Y-2Y): {spread:+.2f}")

    # Real yield 10Y (nominal 10Y - inflacja YoY) – kontekst dla GOLD
    cpi_df = get_fred("CPIAUCSL", limit=14)
    if cpi_df is not None and len(cpi_df) >= 13 and results.get("US10Y"):
        cpi_now = cpi_df["value"].iloc[-1]
        cpi_12m = cpi_df["value"].iloc[-13]
        cpi_yoy = (cpi_now / cpi_12m - 1) * 100 if cpi_12m else 0
        results["CPI_YoY"] = round(cpi_yoy, 2)
        real_10y = results["US10Y"]["value"] - cpi_yoy
        results["REAL_YIELD_10Y"] = round(real_10y, 2)
        print(f"   [*] Real yield 10Y (nominal - CPI YoY): {real_10y:+.2f}%")

    # Risk On/Off Score (0-20)
    if results.get("DXY"):
        dxy_trend = results["DXY"]["trend"]
        score += 5 if dxy_trend == "DOWN" else -5  # DXY down = risk on

    if results.get("US10Y"):
        y10_val = results["US10Y"]["value"]
        score += 5 if y10_val < 4.5 else 0  # Niższe stopy = lepiej dla rynku

    results["macro_score"] = max(0, min(20, score + 10))
    results["timestamp"]   = datetime.now().strftime("%Y-%m-%d %H:%M")
    return results


if __name__ == "__main__":
    data = analyze_macro()
    print(f"\n{'='*45}")
    print(f"{'RAPORT MAKRO':^45}")
    print(f"{'='*45}")
    for k, v in data.items():
        if isinstance(v, dict):
            print(f"{k:<15} {v['value']:<10} trend: {v['trend']}")
        elif k not in ["timestamp"]:
            print(f"{k:<15} {v}")
    print(f"{'='*45}")