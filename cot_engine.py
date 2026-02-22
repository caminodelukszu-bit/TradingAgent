# =============================================================================
# cot_engine.py - COT w ujęciu historycznym (ekstrema 1–3 lat, dynamika 3–4 tyg)
# Źródło: CFTC. Archiwum: cot_archive.db (26–156 tygodni dla AI i wniosków).
# =============================================================================

import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Dwie osobne bazy CFTC
URL_COMMODITIES = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
URL_CURRENCIES  = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"

INSTRUMENTS = {
    "EUR":    {"url": URL_CURRENCIES,  "search": "EURO FX"},
    "GBP":    {"url": URL_CURRENCIES,  "search": "BRITISH POUND"},
    "JPY":    {"url": URL_CURRENCIES,  "search": "JAPANESE YEN"},
    "AUD":    {"url": URL_CURRENCIES,  "search": "AUSTRALIAN DOLLAR"},
    "CAD":    {"url": URL_CURRENCIES,  "search": "CANADIAN DOLLAR"},
    "CHF":    {"url": URL_CURRENCIES,  "search": "SWISS FRANC"},
    "NZD":    {"url": URL_CURRENCIES,  "search": "NEW ZEALAND DOLLAR"},
    "GOLD":   {"url": URL_COMMODITIES, "search": "GOLD"},
    "SILVER": {"url": URL_COMMODITIES, "search": "SILVER"},
    "OIL":    {"url": URL_COMMODITIES, "search": "CRUDE OIL"},
    "COPPER": {"url": URL_COMMODITIES, "search": "COPPER"},
}

# Min. tygodni do sensownej analizy historycznej (6 mies.)
MIN_WEEKS_HISTORY = 26
# Zalecany zakres do ekstremów (1–3 lata)
PREFERRED_WEEKS_1Y = 52
PREFERRED_WEEKS_3Y = 156


def fetch_all_records(url: str, limit: int = 5000) -> list:
    full_url = f"{url}?%24limit={limit}&%24order=report_date_as_yyyy_mm_dd%20DESC"
    r = requests.get(full_url, timeout=30)
    if r.status_code == 200:
        return r.json()
    r = requests.get(url, timeout=30)
    return r.json() if r.status_code == 200 else []


def _fetch_cot_from_api(instrument: str, weeks: int = 156) -> pd.DataFrame | None:
    """Pobiera surowe dane z CFTC i zwraca DataFrame (date, net_position, net_change, oi, oi_change, long_all, short_all)."""
    cfg = INSTRUMENTS.get(instrument.upper())
    if not cfg:
        return None
    all_data = fetch_all_records(cfg["url"])
    if not all_data:
        return None
    search = cfg["search"].lower()
    filtered = [d for d in all_data if search in d.get("market_and_exchange_names", "").lower()]
    if not filtered:
        return None
    filtered = filtered[:weeks]
    df = pd.DataFrame(filtered)
    for col_l, col_s in [
        ("noncomm_positions_long_all", "noncomm_positions_short_all"),
        ("lev_money_positions_long_all", "lev_money_positions_short_all"),
    ]:
        if col_l in df.columns and col_s in df.columns:
            df[col_l] = pd.to_numeric(df[col_l], errors="coerce")
            df[col_s] = pd.to_numeric(df[col_s], errors="coerce")
            df["net_position"] = df[col_l] - df[col_s]
            df["long_all"] = df[col_l]
            df["short_all"] = df[col_s]
            break
    else:
        return None
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    df = df.sort_values("date").reset_index(drop=True)
    df["net_change"] = df["net_position"].diff()
    if "open_interest_all" in df.columns:
        df["oi"] = pd.to_numeric(df["open_interest_all"], errors="coerce")
        df["oi_change"] = df["oi"].diff()
    else:
        df["oi"] = 0
        df["oi_change"] = 0
    return df


def get_cot_data(instrument: str, weeks: int = 156, use_archive_first: bool = True) -> pd.DataFrame | None:
    """
    Zwraca serię COT: najpierw z archiwum (cot_archive), jeśli za mało danych – z API CFTC + zapis do archiwum.
    weeks: 26 = 6 mies., 52 = 1 rok, 156 = 3 lata.
    """
    try:
        from cot_archive import get_cot_history, upsert_cot_series
    except ImportError:
        use_archive_first = False
    if use_archive_first:
        df = get_cot_history(instrument, weeks)
        if df is not None and len(df) >= MIN_WEEKS_HISTORY:
            print(f"   [COT] {instrument}: {len(df)} tygodni z archiwum | Net: {int(df['net_position'].iloc[-1]):,}")
            return df
    print(f"   Pobieram dane z CFTC ({instrument})...")
    df = _fetch_cot_from_api(instrument, weeks)
    if df is None or len(df) < 10:
        return df
    print(f"   [OK] {instrument}: {len(df)} tygodni | Net: {int(df['net_position'].iloc[-1]):,}")
    if use_archive_first:
        try:
            n = upsert_cot_series(instrument, df)
            if n:
                print(f"   [COT] Zapisano do archiwum: {n} tygodni.")
        except Exception as e:
            print(f"   [COT] Archiwum (pomijam): {e}")
    return df


def _percentile_of_score(series: pd.Series, value: float) -> float:
    """Percentyl: jaki % wartości w series jest <= value (0–100)."""
    if series is None or len(series) == 0 or pd.isna(value):
        return 50.0
    return float(np.sum(series <= value) / len(series) * 100)


def calculate_cot_score(df: pd.DataFrame, lookback_1y: int = 52, lookback_2y: int = 104) -> dict:
    """
    Analiza w stylu rekomendowanym: ekstrema na tle 1–3 lat, dynamika 3–4 tygodni.
    - percentile_1y / percentile_2y: gdzie obecna pozycja netto vs historia (ekstremum długie ≈ szczyt, krótkie ≈ dołek).
    - extreme_type: None | "extreme_long" | "extreme_short" gdy percentyl poza 10–90.
    - trend_4w: suma zmian netto w ostatnich 4 tygodniach; szybkie zmiany = potencjalny zwrot.
    Zachowuje kompatybilność: score, bias, momentum, zscore, extreme_warning.
    """
    empty = {
        "score": 0, "bias": "NEUTRAL", "momentum": "BRAK DANYCH", "zscore": 0,
        "net_position": 0, "net_change": 0, "oi": 0, "extreme_warning": False,
        "percentile_1y": 50, "percentile_2y": 50, "extreme_type": None,
        "trend_4w_sum": 0, "trend_4w_direction": "NEUTRAL",
        "cot_interpretation": "Brak wystarczającej historii COT.",
        "weeks_used": 0,
    }
    if df is None or len(df) < MIN_WEEKS_HISTORY:
        return empty
    latest = df.iloc[-1]
    current_net = latest["net_position"]
    if pd.isna(current_net):
        return empty
    # Okno 1 rok i 2 lata (ile mamy)
    series_1y = df["net_position"].tail(lookback_1y)
    series_2y = df["net_position"].tail(min(lookback_2y, len(df)))
    pct_1y = _percentile_of_score(series_1y, current_net)
    pct_2y = _percentile_of_score(series_2y, current_net) if len(series_2y) >= 26 else pct_1y
    # Ekstrema: górne 10% = extreme_long (historycznie często szczyt), dolne 10% = extreme_short (dołek)
    extreme_long = pct_1y >= 90
    extreme_short = pct_1y <= 10
    if extreme_long:
        extreme_type = "extreme_long"
        extreme_warning = True
    elif extreme_short:
        extreme_type = "extreme_short"
        extreme_warning = True
    else:
        extreme_type = None
        extreme_warning = abs(pct_1y - 50) > 40  # zbliżenie do ekstremum
    # Dynamika 3–4 tygodni (szybkie zmiany = zapowiedź zwrotu)
    last_4 = df.tail(4)
    changes = last_4["net_change"].dropna()
    trend_4w_sum = float(changes.sum()) if len(changes) else 0
    if trend_4w_sum > 0:
        trend_4w_dir = "BULLISH"
    elif trend_4w_sum < 0:
        trend_4w_dir = "BEARISH"
    else:
        trend_4w_dir = "NEUTRAL"
    # Momentum (jak wcześniej: 3 z 4 tygodni w jedną stronę)
    positive = sum(1 for c in changes if c > 0)
    negative = sum(1 for c in changes if c < 0)
    if positive >= 3:
        mb = "BULLISH"
    elif negative >= 3:
        mb = "BEARISH"
    else:
        mb = "MIXED"
    # Z-score dla kompatybilności
    mean_net = df["net_position"].mean()
    std_net = df["net_position"].std()
    zscore = (float(current_net) - mean_net) / std_net if std_net and std_net != 0 else 0
    # Score: ekstremum = ważna informacja (nie kara); dynamika 4w wzmacnia
    score = 5
    if extreme_long:
        score += 8
        bias = "SELL"   # ekstremalnie długie pozycje często zwiastują szczyt
    elif extreme_short:
        score += 8
        bias = "BUY"    # ekstremalnie krótkie – dołek
    else:
        if mb == "BULLISH" and zscore < 1.5:
            score += 8
            bias = "BUY"
        elif mb == "BEARISH" and zscore > -1.5:
            score += 8
            bias = "SELL"
        else:
            score += 2
            bias = "NEUTRAL"
    if trend_4w_dir == mb and mb != "MIXED":
        score += 4
    score = min(20, round(score))
    # Interpretacja dla raportu / AI
    if extreme_long:
        interp = f"Pozycja netto w górnych {100 - pct_1y:.0f}% ostatniego roku – ekstremum długie (historycznie często szczyt)."
    elif extreme_short:
        interp = f"Pozycja netto w dolnych {pct_1y:.0f}% ostatniego roku – ekstremum krótkie (historycznie często dołek)."
    else:
        interp = f"Pozycja netto: percentyl 1Y = {pct_1y:.0f}%, 2Y = {pct_2y:.0f}%. Dynamika 4 tyg: {trend_4w_dir} (suma zmian: {trend_4w_sum:,.0f})."
    return {
        "score": score,
        "bias": bias,
        "momentum": mb,
        "zscore": round(zscore, 2),
        "net_position": int(current_net),
        "net_change": int(latest["net_change"]) if pd.notna(latest.get("net_change")) else 0,
        "oi": int(latest["oi"]) if pd.notna(latest.get("oi")) else 0,
        "extreme_warning": extreme_warning,
        "percentile_1y": round(pct_1y, 1),
        "percentile_2y": round(pct_2y, 1),
        "extreme_type": extreme_type,
        "trend_4w_sum": round(trend_4w_sum, 0),
        "trend_4w_direction": trend_4w_dir,
        "cot_interpretation": interp,
        "weeks_used": len(df),
    }


def analyze_cot(instrument: str, weeks: int = 156) -> dict:
    """Główna funkcja: dane z archiwum/API + analiza ekstremów i dynamiki."""
    print(f"\n[COT] Analizuję: {instrument}")
    df = get_cot_data(instrument, weeks=weeks, use_archive_first=True)
    result = calculate_cot_score(df)
    result["instrument"] = instrument
    result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return result


if __name__ == "__main__":
    wyniki = []
    for instr in ["EUR", "JPY", "GBP", "GOLD", "SILVER"]:
        r = analyze_cot(instr)
        wyniki.append(r)
    print(f"\n{'='*70}")
    print("RAPORT COT (ekstrema vs 1Y, dynamika 4 tyg)")
    print(f"{'='*70}")
    print(f"{'PARA':<8} {'BIAS':<8} {'SCORE':<6} {'PCT 1Y':<8} {'EKSTREMUM':<12} {'TREND 4W'}")
    print("-" * 70)
    for r in wyniki:
        ex = r.get("extreme_type") or "-"
        print(f"{r['instrument']:<8} {r['bias']:<8} {r['score']}/20  {r.get('percentile_1y', 0):.0f}%     {ex:<12} {r.get('trend_4w_direction', '')}")
    print("=" * 70)
    for r in wyniki:
        if r.get("cot_interpretation"):
            print(f"  {r['instrument']}: {r['cot_interpretation']}")
