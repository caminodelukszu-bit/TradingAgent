# =============================================================================
# regime_engine.py - Layer 2 (czesc techniczna): Market Regime Filter
# Trading Agent v3.0
#
# Analiza techniczna HTF (Higher Time Frame):
# - 40 EMA Weekly (kluczowy filtr z dokumentu kolegi)
# - Struktura HH/HL (Higher High/Higher Low = trend UP)
#           lub LH/LL (Lower High/Lower Low = trend DOWN)
# - ATR expansion (trend) vs ATR compression (range)
# - OI behavior (z danych COT)
#
# Tickery yfinance dla par walutowych:
# EUR=EURUSD=X | GBP=GBPUSD=X | JPY=USDJPY=X | AUD=AUDUSD=X
# CAD=USDCAD=X | CHF=USDCHF=X | GOLD=GC=F | SILVER=SI=F | BTC=BTC-USD
#
# Output: Regime Type, Trend Confidence Score (0-20), Range Warning Flag
# =============================================================================

import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# =============================================================================
# KONFIGURACJA TICKEROW
# =============================================================================

# Mapowanie waluta -> ticker yfinance (dane tygodniowe)
TICKER_MAP = {
    "EUR":    "EURUSD=X",
    "GBP":    "GBPUSD=X",
    "JPY":    "USDJPY=X",   # odwrocony - USD jest baza
    "AUD":    "AUDUSD=X",
    "CAD":    "USDCAD=X",   # odwrocony - USD jest baza
    "CHF":    "USDCHF=X",   # odwrocony - USD jest baza
    "GOLD":   "GC=F",
    "SILVER": "SI=F",
    "BTC":    "BTC-USD",
}

# Waluty gdzie USD jest BAZA (cena odwrocona - wzrost tickera = slabniecie waluty)
USD_BAZA = ["JPY", "CAD", "CHF"]

# Parametry techniczne
EMA_OKRES    = 40    # 40 EMA Weekly - kluczowy filtr z dokumentu
ATR_OKRES    = 14    # ATR 14 tygodni
SWINGS_OKRES = 52    # 52 tygodnie = 1 rok do wyznaczania swing high/low
MIN_TYGODNI  = 60    # minimalna liczba tygodni danych

# =============================================================================
# POBIERANIE DANYCH TYGODNIOWYCH
# =============================================================================

def pobierz_dane_weekly(waluta, tygodnie=80, use_archive_first: bool = True):
    """
    Pobiera dane tygodniowe (OHLCV). Najpierw z archiwum (history_archive), potem yfinance + zapis.
    Zwraca DataFrame lub None jesli blad.
    """
    if use_archive_first:
        try:
            from history_archive import get_history_regime, upsert_regime_ohlc
            df = get_history_regime(waluta, weeks=min(tygodnie + 20, 200))
            if df is not None and len(df) >= 20:
                return df
        except ImportError:
            pass
    ticker = TICKER_MAP.get(waluta)
    if not ticker:
        print(f"  [REGIME] Brak tickera dla: {waluta}")
        return None
    try:
        koniec = datetime.today()
        start  = koniec - timedelta(weeks=tygodnie + 5)
        dane   = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=koniec.strftime("%Y-%m-%d"),
            interval="1wk",
            progress=False,
            auto_adjust=True
        )
        if dane.empty or len(dane) < 20:
            print(f"  [REGIME] Za malo danych weekly dla {waluta} ({ticker})")
            return None
        if use_archive_first:
            try:
                from history_archive import upsert_regime_ohlc
                upsert_regime_ohlc(waluta, dane)
            except Exception:
                pass
        return dane
    except Exception as e:
        print(f"  [REGIME] BLAD pobierania weekly {waluta}: {e}")
        return None


# =============================================================================
# OBLICZANIE 40 EMA WEEKLY
# =============================================================================

def oblicz_ema(close_arr, okres):
    """
    Oblicza EMA (Exponential Moving Average) dla tablicy cen.
    Zwraca tablice wartosci EMA.
    """
    if len(close_arr) < okres:
        return np.array([np.nan] * len(close_arr))

    ema = np.zeros(len(close_arr))
    k   = 2.0 / (okres + 1)

    # Inicjalizacja pierwszej wartosci EMA jako SMA
    ema[okres - 1] = np.mean(close_arr[:okres])

    for i in range(okres, len(close_arr)):
        ema[i] = close_arr[i] * k + ema[i - 1] * (1 - k)

    # Zerowanie przed pierwsza wartoscia
    ema[:okres - 1] = np.nan
    return ema


def analiza_ema40(dane, waluta):
    """
    Sprawdza polozenie ceny wzgledem 40 EMA Weekly.
    Dla walut z USD jako baza (JPY, CAD, CHF) kierunek jest odwrocony.

    Zwraca slownik z wynikami.
    """
    if dane is None or len(dane) < EMA_OKRES + 5:
        return {
            "ema40":           None,
            "cena":            None,
            "powyzej_ema":     None,
            "odleglosc_pct":   0,
            "ema_kierunek":    "NIEZNANY",
            "sygnal":          0,
            "opis":            "Brak danych EMA40"
        }

    try:
        close = dane["Close"].values.flatten().astype(float)
        ema40 = oblicz_ema(close, EMA_OKRES)

        cena_aktualna = float(close[-1])
        ema_aktualna  = float(ema40[-1])
        ema_poprzednia = float(ema40[-2]) if len(ema40) > 1 else ema_aktualna

        if np.isnan(ema_aktualna):
            return {
                "ema40": None, "cena": cena_aktualna,
                "powyzej_ema": None, "odleglosc_pct": 0,
                "ema_kierunek": "NIEZNANY", "sygnal": 0,
                "opis": "EMA40 - za malo danych"
            }

        # Odleglosc ceny od EMA w procentach
        odleglosc_pct = ((cena_aktualna - ema_aktualna) / ema_aktualna) * 100

        # Kierunek EMA (rosnie/spada)
        ema_slope = ema_aktualna - ema_poprzednia
        if ema_slope > 0:
            ema_kierunek = "ROSNIE"
        elif ema_slope < 0:
            ema_kierunek = "SPADA"
        else:
            ema_kierunek = "PLASKA"

        # Dla walut gdzie USD jest baza - odwracamy interpretacje
        # np. USDJPY rosnie = JPY SLABNIE = dla JPY to jest BEARISH
        if waluta in USD_BAZA:
            powyzej_ema  = cena_aktualna < ema_aktualna  # odwrocone
            odleglosc_pct = -odleglosc_pct               # odwrocone
            ema_kierunek_waluta = "SPADA" if ema_kierunek == "ROSNIE" else ("ROSNIE" if ema_kierunek == "SPADA" else "PLASKA")
        else:
            powyzej_ema  = cena_aktualna > ema_aktualna
            ema_kierunek_waluta = ema_kierunek

        # Sygnal: +1 bullish, -1 bearish, 0 neutralny
        if powyzej_ema and ema_kierunek_waluta == "ROSNIE":
            sygnal = 1
            opis   = f"Cena POWYZEJ 40EMA i EMA rosnie ({odleglosc_pct:+.2f}%) - BULLISH"
        elif powyzej_ema and ema_kierunek_waluta == "PLASKA":
            sygnal = 1
            opis   = f"Cena POWYZEJ 40EMA (EMA plaska) ({odleglosc_pct:+.2f}%)"
        elif not powyzej_ema and ema_kierunek_waluta == "SPADA":
            sygnal = -1
            opis   = f"Cena PONIZEJ 40EMA i EMA spada ({odleglosc_pct:+.2f}%) - BEARISH"
        elif not powyzej_ema and ema_kierunek_waluta == "PLASKA":
            sygnal = -1
            opis   = f"Cena PONIZEJ 40EMA (EMA plaska) ({odleglosc_pct:+.2f}%)"
        elif powyzej_ema and ema_kierunek_waluta == "SPADA":
            sygnal = 0
            opis   = f"Cena POWYZEJ 40EMA ale EMA spada - UWAGA sygnaly sprzeczne"
        else:
            sygnal = 0
            opis   = f"Cena PONIZEJ 40EMA ale EMA rosnie - mozliwe odwrocenie"

        return {
            "ema40":          round(ema_aktualna, 5),
            "cena":           round(cena_aktualna, 5),
            "powyzej_ema":    powyzej_ema,
            "odleglosc_pct":  round(odleglosc_pct, 3),
            "ema_kierunek":   ema_kierunek_waluta,
            "sygnal":         sygnal,
            "opis":           opis
        }

    except Exception as e:
        print(f"  [REGIME] BLAD EMA40 dla {waluta}: {e}")
        return {
            "ema40": None, "cena": None, "powyzej_ema": None,
            "odleglosc_pct": 0, "ema_kierunek": "NIEZNANY",
            "sygnal": 0, "opis": f"Blad obliczen: {e}"
        }


# =============================================================================
# STRUKTURA RYNKU - HH/HL vs LH/LL
# =============================================================================

def znajdz_swing_points(dane, okno=3):
    """
    Wykrywa punkty zwrotne (swing high / swing low) na danych tygodniowych.
    Okno = ile swiec po obu stronach musi byc nizszych/wyzszych.
    Zwraca liste swing_high i swing_low jako indeksy.
    """
    if dane is None or len(dane) < okno * 2 + 1:
        return [], []

    high  = dane["High"].values.flatten().astype(float)
    low   = dane["Low"].values.flatten().astype(float)

    swing_highs = []
    swing_lows  = []

    for i in range(okno, len(high) - okno):
        # Swing High: najwyzszy w oknie
        if all(high[i] >= high[i - j] for j in range(1, okno + 1)) and \
           all(high[i] >= high[i + j] for j in range(1, okno + 1)):
            swing_highs.append((i, high[i]))

        # Swing Low: najnizszy w oknie
        if all(low[i] <= low[i - j] for j in range(1, okno + 1)) and \
           all(low[i] <= low[i + j] for j in range(1, okno + 1)):
            swing_lows.append((i, low[i]))

    return swing_highs, swing_lows


def analiza_struktury_rynku(dane, waluta):
    """
    Analizuje strukture rynku HTF:
    - HH + HL = trend UP (Higher Highs + Higher Lows)
    - LH + LL = trend DOWN (Lower Highs + Lower Lows)
    - Brak jasnej struktury = RANGE lub AKUMULACJA/DYSTRYBUCJA

    Zwraca typ struktury i sygnal kierunkowy.
    """
    if dane is None or len(dane) < 20:
        return {
            "struktura":  "NIEZNANA",
            "sygnal":     0,
            "ostatni_sh": None,
            "ostatni_sl": None,
            "opis":       "Brak danych struktury"
        }

    try:
        swing_highs, swing_lows = znajdz_swing_points(dane, okno=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                "struktura": "BRAK STRUKTURY",
                "sygnal":    0,
                "opis":      "Za malo punktow zwrotnych do oceny"
            }

        # Ostatnie 3 swing highs i swing lows
        ostatnie_sh = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        ostatnie_sl = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

        # Dla walut z USD jako baza - odwracamy
        if waluta in USD_BAZA:
            # HH w USDJPY = LH dla JPY (USD rosnie = JPY spada)
            sh_wartosci = [s[1] for s in ostatnie_sh]
            sl_wartosci = [s[1] for s in ostatnie_sl]
            # Odwracamy kierunek
            sh_trend = "DOWN" if sh_wartosci[-1] > sh_wartosci[0] else "UP"
            sl_trend = "DOWN" if sl_wartosci[-1] > sl_wartosci[0] else "UP"
        else:
            sh_wartosci = [s[1] for s in ostatnie_sh]
            sl_wartosci = [s[1] for s in ostatnie_sl]
            sh_trend = "UP" if sh_wartosci[-1] > sh_wartosci[0] else "DOWN"
            sl_trend = "UP" if sl_wartosci[-1] > sl_wartosci[0] else "DOWN"

        # Ocena struktury
        if sh_trend == "UP" and sl_trend == "UP":
            struktura = "TRENDING UP (HH+HL)"
            sygnal    = 1
            opis      = "Struktura bullish: Higher Highs + Higher Lows"
        elif sh_trend == "DOWN" and sl_trend == "DOWN":
            struktura = "TRENDING DOWN (LH+LL)"
            sygnal    = -1
            opis      = "Struktura bearish: Lower Highs + Lower Lows"
        elif sh_trend == "UP" and sl_trend == "DOWN":
            struktura = "ROZSZERZAJACY SIE (expansion)"
            sygnal    = 0
            opis      = "Wiekszy zakres oscylacji - mozliwy poczatek trendu lub zmiennosc"
        elif sh_trend == "DOWN" and sl_trend == "UP":
            struktura = "ZWEZAJACY SIE (compression/range)"
            sygnal    = 0
            opis      = "Zawezanie zakresu - akumulacja lub dystrybucja przed wybiciem"
        else:
            struktura = "NIEJEDNOZNACZNA"
            sygnal    = 0
            opis      = "Struktura niejednoznaczna"

        return {
            "struktura":  struktura,
            "sygnal":     sygnal,
            "ostatni_sh": round(float(sh_wartosci[-1]), 5) if sh_wartosci else None,
            "ostatni_sl": round(float(sl_wartosci[-1]), 5) if sl_wartosci else None,
            "sh_trend":   sh_trend,
            "sl_trend":   sl_trend,
            "opis":       opis
        }

    except Exception as e:
        print(f"  [REGIME] BLAD struktury {waluta}: {e}")
        return {"struktura": "BLAD", "sygnal": 0, "opis": str(e)}


# =============================================================================
# ATR - EXPANSION VS COMPRESSION
# =============================================================================

def analiza_atr(dane, waluta):
    """
    Oblicza ATR (Average True Range) i ocenia czy rynek jest:
    - ATR EXPANSION = trend aktywny (duza zmiennosc)
    - ATR COMPRESSION = range / konsolidacja (mala zmiennosc)

    Porownuje obecny ATR do sredniej z ostatnich 52 tygodni.
    """
    if dane is None or len(dane) < ATR_OKRES + 10:
        return {
            "atr_aktualny":  0,
            "atr_srednia":   0,
            "atr_ratio":     1.0,
            "stan":          "NIEZNANY",
            "sygnal":        0,
            "opis":          "Brak danych ATR"
        }

    try:
        high  = dane["High"].values.flatten().astype(float)
        low   = dane["Low"].values.flatten().astype(float)
        close = dane["Close"].values.flatten().astype(float)

        # True Range
        tr = np.zeros(len(close))
        for i in range(1, len(close)):
            hl   = high[i] - low[i]
            hc   = abs(high[i] - close[i - 1])
            lc   = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        # ATR jako srednia krocząca TR
        atr = np.zeros(len(tr))
        for i in range(ATR_OKRES, len(tr)):
            atr[i] = np.mean(tr[i - ATR_OKRES + 1:i + 1])

        # Porownaj obecny ATR do sredniej z ostatnich 52 tygodni
        atr_aktualny = float(atr[-1])
        dlugosc      = min(52, len(atr))
        atr_srednia  = float(np.mean(atr[-dlugosc:][atr[-dlugosc:] > 0]))

        if atr_srednia == 0:
            return {
                "atr_aktualny": 0, "atr_srednia": 0,
                "atr_ratio": 1.0, "stan": "NIEZNANY",
                "sygnal": 0, "opis": "ATR srednia = 0"
            }

        atr_ratio = atr_aktualny / atr_srednia

        # Percentyl ATR (obecny ATR vs rozkład ostatnich 52)
        atr_valid = atr[-52:][atr[-52:] > 0]
        atr_percentile = None
        if len(atr_valid) >= 10:
            atr_percentile = round(float(100 * (atr_valid < atr_aktualny).sum() / len(atr_valid)), 0)

        # Ocena ATR
        if atr_ratio > 1.3:
            stan   = "SILNA EKSPANSJA"
            sygnal = 1   # trend aktywny
            opis   = f"ATR expansion silna ({atr_ratio:.2f}x sredniej) - trend aktywny"
        elif atr_ratio > 1.1:
            stan   = "EKSPANSJA"
            sygnal = 1
            opis   = f"ATR expansion ({atr_ratio:.2f}x sredniej) - ruch kierunkowy"
        elif atr_ratio < 0.7:
            stan   = "SILNA KOMPRESJA"
            sygnal = -1  # range - kara punktowa
            opis   = f"ATR kompresja silna ({atr_ratio:.2f}x sredniej) - konsolidacja/range"
        elif atr_ratio < 0.9:
            stan   = "KOMPRESJA"
            sygnal = -1
            opis   = f"ATR kompresja ({atr_ratio:.2f}x sredniej) - zasieg ograniczony"
        else:
            stan   = "NORMALNY"
            sygnal = 0
            opis   = f"ATR normalny ({atr_ratio:.2f}x sredniej)"

        out = {
            "atr_aktualny": round(atr_aktualny, 6),
            "atr_srednia":  round(atr_srednia, 6),
            "atr_ratio":    round(atr_ratio, 3),
            "stan":         stan,
            "sygnal":       sygnal,
            "opis":         opis
        }
        if atr_percentile is not None:
            out["atr_percentile"] = atr_percentile
        return out

    except Exception as e:
        print(f"  [REGIME] BLAD ATR {waluta}: {e}")
        return {
            "atr_aktualny": 0, "atr_srednia": 0,
            "atr_ratio": 1.0, "stan": "BLAD",
            "sygnal": 0, "opis": str(e)
        }


# =============================================================================
# GLOWNA FUNKCJA - REGIME PER WALUTA
# =============================================================================

def get_regime(waluta, cot_oi_rosnie=None):
    """
    Glowna funkcja - analizuje rezim techniczny dla danej waluty.
    Laczy EMA40 + Strukture HH/HL + ATR w jeden wynik.

    Parametr cot_oi_rosnie: opcjonalnie z cot_engine - czy OI rosnie.

    Zwraca slownik z pelnymi wynikami i score 0-20.
    """
    print(f"  [REGIME] Analizuje rezim: {waluta}")

    dane = pobierz_dane_weekly(waluta)

    ema_wynik       = analiza_ema40(dane, waluta)
    struktura_wynik = analiza_struktury_rynku(dane, waluta)
    atr_wynik       = analiza_atr(dane, waluta)

    # Pozycja ceny w zakresie 52w (0 = dno, 100 = szczyt)
    range_52w_pct = None
    if dane is not None and len(dane) >= 52:
        try:
            high_52 = dane["High"].values.flatten().astype(float)[-52:].max()
            low_52  = dane["Low"].values.flatten().astype(float)[-52:].min()
            close   = float(dane["Close"].values.flatten().astype(float)[-1])
            if high_52 > low_52:
                range_52w_pct = round((close - low_52) / (high_52 - low_52) * 100, 0)
            else:
                range_52w_pct = 50.0
        except Exception:
            pass

    # ==========================================================
    # SCORING WARSTWY 2 TECHNICZNEJ (0-20 pkt)
    # ==========================================================
    score = 10  # baza neutralna

    # --- EMA40 (max +/-6 pkt) ---
    ema_sygnal = ema_wynik.get("sygnal", 0)
    if ema_sygnal == 1:
        score += 6
    elif ema_sygnal == -1:
        score -= 6

    # --- Struktura HH/HL (max +/-5 pkt) ---
    struct_sygnal = struktura_wynik.get("sygnal", 0)
    if struct_sygnal == 1:
        score += 5
    elif struct_sygnal == -1:
        score -= 5

    # --- ATR (max +/-3 pkt + kara za range) ---
    atr_sygnal = atr_wynik.get("sygnal", 0)
    if atr_sygnal == 1:
        score += 3
    elif atr_sygnal == -1:
        score -= 3  # range = kara

    # --- OI zachowanie (opcjonalne +/-2 pkt) ---
    if cot_oi_rosnie is True:
        score += 2
    elif cot_oi_rosnie is False:
        score -= 2

    score = max(0, min(20, score))

    # ==========================================================
    # TYP REZIMU
    # ==========================================================
    ema_s    = ema_wynik.get("sygnal", 0)
    struct_s = struktura_wynik.get("sygnal", 0)
    atr_s    = atr_wynik.get("sygnal", 0)
    struktura = struktura_wynik.get("struktura", "NIEZNANA")

    if ema_s == 1 and struct_s == 1 and atr_s >= 0:
        typ_rezimu    = "TRENDING BULLISH"
        range_warning = False
    elif ema_s == -1 and struct_s == -1 and atr_s >= 0:
        typ_rezimu    = "TRENDING BEARISH"
        range_warning = False
    elif atr_s == -1 or "ZWEZAJACY" in struktura or "COMPRESSION" in atr_wynik.get("stan", ""):
        typ_rezimu    = "RANGE"
        range_warning = True
    elif ema_s == 1 and struct_s == -1:
        typ_rezimu    = "DYSTRYBUCJA"
        range_warning = False
    elif ema_s == -1 and struct_s == 1:
        typ_rezimu    = "AKUMULACJA"
        range_warning = False
    elif "ROZSZERZAJACY" in struktura:
        typ_rezimu    = "HIGH VOLATILITY MACRO REGIME"
        range_warning = False
    else:
        typ_rezimu    = "NEUTRALNY"
        range_warning = False

    # Kara za range (-10 pkt z dokumentu kolegi)
    kara_range = -10 if range_warning else 0

    # ==========================================================
    # WYNIK FINALNY
    # ==========================================================
    wynik = {
        "score":        score,
        "typ_rezimu":   typ_rezimu,
        "range_warning": range_warning,
        "kara_range":   kara_range,

        # EMA40
        "ema40":           ema_wynik.get("ema40"),
        "cena":            ema_wynik.get("cena"),
        "powyzej_ema":     ema_wynik.get("powyzej_ema"),
        "ema_odleglosc":   ema_wynik.get("odleglosc_pct"),
        "ema_kierunek":    ema_wynik.get("ema_kierunek"),
        "ema_sygnal":      ema_wynik.get("sygnal"),
        "ema_opis":        ema_wynik.get("opis"),

        # Struktura
        "struktura":       struktura_wynik.get("struktura"),
        "struct_sygnal":   struktura_wynik.get("sygnal"),
        "struct_opis":     struktura_wynik.get("opis"),
        "ostatni_sh":      struktura_wynik.get("ostatni_sh"),
        "ostatni_sl":      struktura_wynik.get("ostatni_sl"),

        # ATR
        "atr_stan":         atr_wynik.get("stan"),
        "atr_ratio":        atr_wynik.get("atr_ratio"),
        "atr_sygnal":       atr_wynik.get("sygnal"),
        "atr_opis":         atr_wynik.get("opis"),
        "atr_percentile":   atr_wynik.get("atr_percentile"),
        "range_52w_pct":    range_52w_pct,

        "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    print(f"         EMA40:     {ema_wynik.get('opis','?')}")
    print(f"         Struktura: {struktura_wynik.get('opis','?')}")
    print(f"         ATR:       {atr_wynik.get('opis','?')}")
    print(f"         Rezim:     {typ_rezimu} | Score: {score}/20")
    if range_warning:
        print(f"         [!] RANGE WARNING - kara {kara_range} pkt")

    return wynik


def analizuj_wszystkie_rezimy(instrumenty=None):
    """
    Analizuje rezim techniczny dla wszystkich instrumentow.
    Uzywane przez main.py do pobrania rezimu raz dla wszystkich.
    """
    if instrumenty is None:
        instrumenty = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "GOLD", "SILVER", "BTC"]

    print("\n" + "=" * 60)
    print("LAYER 2 (tech): MARKET REGIME ENGINE")
    print("=" * 60)
    print("Pobieranie danych Weekly przez yfinance...")

    wyniki = {}
    for inst in instrumenty:
        wyniki[inst] = get_regime(inst)

    return wyniki


def formatuj_regime_raport(wyniki_rezimu):
    """
    Formatuje wyniki regime do czytelnego raportu.
    """
    linie = []
    linie.append("--- LAYER 2 (tech): MARKET REGIME ---")
    linie.append(f"  {'WALUTA':<8} {'REZIM':<25} {'EMA40':<10} {'STRUKTURA':<25} {'ATR':<20} {'SCORE'}")
    linie.append(f"  {'-' * 95}")

    for waluta, w in wyniki_rezimu.items():
        ema_tag    = "ABOVE" if w.get("powyzej_ema") else ("BELOW" if w.get("powyzej_ema") is False else "N/A")
        range_tag  = " [RANGE!]" if w.get("range_warning") else ""
        linie.append(
            f"  {waluta:<8} "
            f"{w.get('typ_rezimu','?'):<25} "
            f"{ema_tag:<10} "
            f"{str(w.get('struktura','?'))[:24]:<25} "
            f"{w.get('atr_stan','?'):<20} "
            f"{w.get('score',0)}/20"
            f"{range_tag}"
        )

    return "\n".join(linie)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("TEST: regime_engine.py - Layer 2 Market Regime")
    print("COT is contextual, not predictive.")
    print()

    wyniki = analizuj_wszystkie_rezimy(["EUR", "GBP", "JPY", "AUD", "CAD"])
    print()
    print(formatuj_regime_raport(wyniki))