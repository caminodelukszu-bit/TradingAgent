# =============================================================================
# flow_engine.py - Layer 3: Intermarket Flow Engine
# Trading Agent v3.0
# Analiza przeplywu kapitalow przez ETF proxy (yfinance)
# Output: RISK-ON / RISK-OFF, score 0-20 per waluta
# =============================================================================

import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# =============================================================================
# KONFIGURACJA ETF PROXY
# =============================================================================

ETF_LISTA = {
    "GLD":  "Zloto (risk-off)",
    "TLT":  "Obligacje US dlugterminowe (risk-off)",
    "SPY":  "Akcje US S&P500 (risk-on)",
    "UUP":  "Dolar USD ETF",
    "USO":  "Ropa naftowa",
    "EEM":  "Rynki wschodzace - proxy AUD/CAD (risk-on)",
    "FXE":  "Euro ETF",
    "FXB":  "Funt GBP ETF",
    "FXY":  "Jen JPY ETF",
}

# Okres analizy w dniach
OKRES_KROTKI  = 5   # 1 tydzien
OKRES_SREDNI  = 20  # 1 miesiac
OKRES_DLUGI   = 60  # 3 miesiace

# Prog zmiany procentowej aby uznac ruch za istotny
PROG_ZMIANY_PCT = 0.5  # 0.5%

# =============================================================================
# POBIERANIE DANYCH ETF
# =============================================================================

def pobierz_dane_etf(ticker, dni=65, use_archive_first: bool = True):
    """
    Pobiera dane historyczne ETF. Najpierw z archiwum (history_archive), potem yfinance + zapis.
    Zwraca DataFrame lub None jesli blad.
    """
    if use_archive_first:
        try:
            from history_archive import get_history_flow, upsert_flow_ohlc
            df = get_history_flow(ticker, days=min(dni + 30, 400))
            if df is not None and len(df) >= 5:
                return df
        except ImportError:
            pass
    try:
        koniec = datetime.today()
        start = koniec - timedelta(days=dni + 10)  # zapas na weekendy/swieta
        dane = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=koniec.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True
        )
        if dane.empty or len(dane) < 5:
            print(f"  [FLOW] BRAK DANYCH: {ticker}")
            return None
        if use_archive_first:
            try:
                from history_archive import upsert_flow_ohlc
                upsert_flow_ohlc(ticker, dane)
            except Exception:
                pass
        return dane
    except Exception as e:
        print(f"  [FLOW] BLAD pobierania {ticker}: {e}")
        return None


def oblicz_zmiane_pct(dane, okres):
    """
    Oblicza zmiane procentowa ceny zamkniecia za ostatnie X sesji.
    Zwraca float lub None.
    """
    if dane is None or len(dane) < okres + 1:
        return None
    try:
        close = dane["Close"].values.flatten()
        if len(close) < okres + 1:
            return None
        zmiana = ((close[-1] - close[-(okres + 1)]) / close[-(okres + 1)]) * 100
        return float(zmiana)
    except Exception as e:
        print(f"  [FLOW] BLAD obliczania zmiany: {e}")
        return None


def oblicz_momentum_ma(dane, krotki=5, dlugi=20):
    """
    Sprawdza czy krotka MA jest powyzej dlugiej MA (momentum bullish).
    Zwraca: 1 (bullish), -1 (bearish), 0 (neutralny)
    """
    if dane is None or len(dane) < dlugi + 1:
        return 0
    try:
        close = dane["Close"].values.flatten()
        ma_krotka = np.mean(close[-krotki:])
        ma_dluga  = np.mean(close[-dlugi:])
        if ma_krotka > ma_dluga * 1.001:
            return 1   # bullish
        elif ma_krotka < ma_dluga * 0.999:
            return -1  # bearish
        else:
            return 0   # neutralny
    except Exception as e:
        print(f"  [FLOW] BLAD obliczania MA: {e}")
        return 0


# =============================================================================
# WYKRYWANIE REZIMU RISK-ON / RISK-OFF
# =============================================================================

def wykryj_rezim_rynkowy(dane_etf):
    """
    Analizuje 3 kluczowe korelacje i wykrywa rezim RISK-ON / RISK-OFF.
    Zasada: min. 2 z 3 korelacji musi potwierdzac kierunek.

    RISK-ON:  SPY rosnie, VIX spada (proxy: TLT spada), EEM rosnie
    RISK-OFF: TLT rosnie, GLD rosnie, VIX/zmiennosc rosnie (SPY spada)

    Zwraca slownik z wynikami.
    """
    wyniki = {
        "rezim":       "NEUTRALNY",
        "sila":        0,
        "spy_signal":  0,
        "tlt_signal":  0,
        "eem_signal":  0,
        "gld_signal":  0,
        "potwierdzenia_risk_on":  0,
        "potwierdzenia_risk_off": 0,
        "opis": []
    }

    # --- Sygnal SPY (akcje US) ---
    zmiana_spy = oblicz_zmiane_pct(dane_etf.get("SPY"), OKRES_KROTKI)
    ma_spy     = oblicz_momentum_ma(dane_etf.get("SPY"))
    if zmiana_spy is not None:
        if zmiana_spy > PROG_ZMIANY_PCT and ma_spy >= 0:
            wyniki["spy_signal"] = 1
            wyniki["opis"].append(f"SPY rosnie ({zmiana_spy:+.2f}%) - RISK-ON")
        elif zmiana_spy < -PROG_ZMIANY_PCT and ma_spy <= 0:
            wyniki["spy_signal"] = -1
            wyniki["opis"].append(f"SPY spada ({zmiana_spy:+.2f}%) - RISK-OFF")
        else:
            wyniki["opis"].append(f"SPY neutralny ({zmiana_spy:+.2f}%)")

    # --- Sygnal TLT (obligacje - bezpieczna przystani) ---
    zmiana_tlt = oblicz_zmiane_pct(dane_etf.get("TLT"), OKRES_KROTKI)
    ma_tlt     = oblicz_momentum_ma(dane_etf.get("TLT"))
    if zmiana_tlt is not None:
        if zmiana_tlt > PROG_ZMIANY_PCT and ma_tlt >= 0:
            wyniki["tlt_signal"] = -1  # TLT w gore = risk-off
            wyniki["opis"].append(f"TLT rosnie ({zmiana_tlt:+.2f}%) - RISK-OFF (bezpieczna przystani)")
        elif zmiana_tlt < -PROG_ZMIANY_PCT and ma_tlt <= 0:
            wyniki["tlt_signal"] = 1   # TLT w dol = risk-on
            wyniki["opis"].append(f"TLT spada ({zmiana_tlt:+.2f}%) - RISK-ON (kapital ucieka z obligacji)")
        else:
            wyniki["opis"].append(f"TLT neutralny ({zmiana_tlt:+.2f}%)")

    # --- Sygnal EEM (rynki wschodzace) ---
    zmiana_eem = oblicz_zmiane_pct(dane_etf.get("EEM"), OKRES_KROTKI)
    ma_eem     = oblicz_momentum_ma(dane_etf.get("EEM"))
    if zmiana_eem is not None:
        if zmiana_eem > PROG_ZMIANY_PCT and ma_eem >= 0:
            wyniki["eem_signal"] = 1
            wyniki["opis"].append(f"EEM rosnie ({zmiana_eem:+.2f}%) - RISK-ON (AUD/CAD pozytywnie)")
        elif zmiana_eem < -PROG_ZMIANY_PCT and ma_eem <= 0:
            wyniki["eem_signal"] = -1
            wyniki["opis"].append(f"EEM spada ({zmiana_eem:+.2f}%) - RISK-OFF (AUD/CAD negatywnie)")
        else:
            wyniki["opis"].append(f"EEM neutralny ({zmiana_eem:+.2f}%)")

    # --- Sygnal GLD (zloto) ---
    zmiana_gld = oblicz_zmiane_pct(dane_etf.get("GLD"), OKRES_KROTKI)
    ma_gld     = oblicz_momentum_ma(dane_etf.get("GLD"))
    if zmiana_gld is not None:
        if zmiana_gld > PROG_ZMIANY_PCT and ma_gld >= 0:
            wyniki["gld_signal"] = -1  # zloto rosnie = risk-off
            wyniki["opis"].append(f"GLD rosnie ({zmiana_gld:+.2f}%) - RISK-OFF (zloto jako bezpieczna przystani)")
        elif zmiana_gld < -PROG_ZMIANY_PCT and ma_gld <= 0:
            wyniki["gld_signal"] = 1   # zloto spada = risk-on (apetyt na ryzyko)
            wyniki["opis"].append(f"GLD spada ({zmiana_gld:+.2f}%) - RISK-ON")
        else:
            wyniki["opis"].append(f"GLD neutralny ({zmiana_gld:+.2f}%)")

    # --- Zliczanie potwierdzen ---
    sygnaly = [wyniki["spy_signal"], wyniki["tlt_signal"], wyniki["eem_signal"], wyniki["gld_signal"]]
    wyniki["potwierdzenia_risk_on"]  = sum(1 for s in sygnaly if s == 1)
    wyniki["potwierdzenia_risk_off"] = sum(1 for s in sygnaly if s == -1)

    # --- Decyzja - min. 2 z 4 musi potwierdzac ---
    if wyniki["potwierdzenia_risk_on"] >= 2:
        wyniki["rezim"] = "RISK-ON"
        wyniki["sila"]  = wyniki["potwierdzenia_risk_on"]
    elif wyniki["potwierdzenia_risk_off"] >= 2:
        wyniki["rezim"] = "RISK-OFF"
        wyniki["sila"]  = wyniki["potwierdzenia_risk_off"]
    else:
        wyniki["rezim"] = "NEUTRALNY"
        wyniki["sila"]  = 0

    return wyniki


# =============================================================================
# ANALIZA SILY DOLARA
# =============================================================================

def analizuj_dolar(dane_etf):
    """
    Analizuje sile dolara przez UUP ETF.
    Zwraca kierunek i sile USD.
    """
    zmiana_uup = oblicz_zmiane_pct(dane_etf.get("UUP"), OKRES_SREDNI)
    ma_uup     = oblicz_momentum_ma(dane_etf.get("UUP"))

    if zmiana_uup is None:
        return {"kierunek": "NIEZNANY", "zmiana": 0.0, "momentum": 0}

    if zmiana_uup > 1.0 and ma_uup == 1:
        kierunek = "MOCNY"
    elif zmiana_uup > 0.3:
        kierunek = "UMIARKOWANIE MOCNY"
    elif zmiana_uup < -1.0 and ma_uup == -1:
        kierunek = "SLABY"
    elif zmiana_uup < -0.3:
        kierunek = "UMIARKOWANIE SLABY"
    else:
        kierunek = "NEUTRALNY"

    return {
        "kierunek": kierunek,
        "zmiana":   round(zmiana_uup, 2),
        "momentum": ma_uup
    }


def analizuj_ropy_i_surowce(dane_etf):
    """
    Analizuje rynek ropy (USO) - proxy dla AUD/CAD/NOK.
    """
    zmiana_uso = oblicz_zmiane_pct(dane_etf.get("USO"), OKRES_SREDNI)
    ma_uso     = oblicz_momentum_ma(dane_etf.get("USO"))

    if zmiana_uso is None:
        return {"kierunek": "NIEZNANY", "zmiana": 0.0, "commodity_bias": 0}

    if zmiana_uso > 2.0:
        kierunek = "SILNY WZROST"
        bias = 1
    elif zmiana_uso > 0.5:
        kierunek = "WZROST"
        bias = 1
    elif zmiana_uso < -2.0:
        kierunek = "SILNY SPADEK"
        bias = -1
    elif zmiana_uso < -0.5:
        kierunek = "SPADEK"
        bias = -1
    else:
        kierunek = "NEUTRALNY"
        bias = 0

    return {
        "kierunek":      kierunek,
        "zmiana":        round(zmiana_uso, 2),
        "commodity_bias": bias
    }


# =============================================================================
# SCORING PER WALUTA (0-20 PKT)
# =============================================================================

def oblicz_score_waluty(waluta, rezim, usd_analiza, surowce_analiza, dane_etf):
    """
    Oblicza Flow Confirmation Score (0-20) dla konkretnej waluty.
    Uwzglednia rezim RISK-ON/RISK-OFF, sile dolara i surowce.

    Logika:
    - Baza: 10 pkt (neutralny)
    - RISK-ON/OFF zgodny z biasem: +4 do +8 pkt
    - USD kierunek zgodny: +2 do +4 pkt
    - Surowce dla AUD/CAD: +2 pkt
    - Dywergencje: kara punktowa
    """

    score = 10  # baza neutralna
    flagi = []
    dywergencja = False

    rezim_typ = rezim.get("rezim", "NEUTRALNY")
    sila_rezimu = rezim.get("sila", 0)
    usd_kierunek = usd_analiza.get("kierunek", "NEUTRALNY")

    # --- EUR ---
    if waluta == "EUR":
        fxe_zmiana = oblicz_zmiane_pct(dane_etf.get("FXE"), OKRES_SREDNI)
        if fxe_zmiana is not None:
            if fxe_zmiana > 0.5:
                score += 3
                flagi.append("FXE rosnie - EUR bullish")
            elif fxe_zmiana < -0.5:
                score -= 3
                flagi.append("FXE spada - EUR bearish")
        if rezim_typ == "RISK-OFF" and usd_kierunek in ["MOCNY", "UMIARKOWANIE MOCNY"]:
            score -= 4
            flagi.append("RISK-OFF + mocny USD = EUR presja spadkowa")
        elif rezim_typ == "RISK-ON" and usd_kierunek in ["SLABY", "UMIARKOWANIE SLABY"]:
            score += 4
            flagi.append("RISK-ON + slaby USD = EUR potencjal wzrostowy")

    # --- GBP ---
    elif waluta == "GBP":
        fxb_zmiana = oblicz_zmiane_pct(dane_etf.get("FXB"), OKRES_SREDNI)
        if fxb_zmiana is not None:
            if fxb_zmiana > 0.5:
                score += 3
                flagi.append("FXB rosnie - GBP bullish")
            elif fxb_zmiana < -0.5:
                score -= 3
                flagi.append("FXB spada - GBP bearish")
        if rezim_typ == "RISK-ON":
            score += 2
            flagi.append("RISK-ON wspiera GBP (waluta pro-cykliczna)")
        elif rezim_typ == "RISK-OFF":
            score -= 2
            flagi.append("RISK-OFF negatywny dla GBP")

    # --- JPY ---
    elif waluta == "JPY":
        fxy_zmiana = oblicz_zmiane_pct(dane_etf.get("FXY"), OKRES_SREDNI)
        if fxy_zmiana is not None:
            if fxy_zmiana > 0.5:
                score += 4
                flagi.append("FXY rosnie - JPY mocny")
            elif fxy_zmiana < -0.5:
                score -= 4
                flagi.append("FXY spada - JPY slaby (carry trade aktywny)")
        if rezim_typ == "RISK-OFF" and sila_rezimu >= 2:
            score += 5
            flagi.append("RISK-OFF silny = JPY bezpieczna przystani - mocny sygnal")
        elif rezim_typ == "RISK-ON":
            score -= 3
            flagi.append("RISK-ON = JPY pod presja (carry trade)")
        tlt_signal = rezim.get("tlt_signal", 0)
        gld_signal = rezim.get("gld_signal", 0)
        if tlt_signal == -1 and fxy_zmiana is not None and fxy_zmiana > 0:
            dywergencja = True
            score -= 3
            flagi.append("DYWERGENCJA: TLT spada ale JPY rosnie - sygnaly sprzeczne")

    # --- CHF ---
    elif waluta == "CHF":
        if rezim_typ == "RISK-OFF" and sila_rezimu >= 2:
            score += 5
            flagi.append("RISK-OFF silny = CHF bezpieczna przystani (jak JPY)")
        elif rezim_typ == "RISK-ON":
            score -= 3
            flagi.append("RISK-ON = CHF pod presja")
        gld_signal = rezim.get("gld_signal", 0)
        if gld_signal == -1:  # zloto rosnie = risk-off
            score += 2
            flagi.append("GLD rosnie - wspiera CHF jako safe haven")

    # --- AUD ---
    elif waluta == "AUD":
        commodity_bias = surowce_analiza.get("commodity_bias", 0)
        if rezim_typ == "RISK-ON" and sila_rezimu >= 2:
            score += 5
            flagi.append("RISK-ON silny = AUD pozytywny (waluta pro-cykliczna)")
        elif rezim_typ == "RISK-ON":
            score += 2
            flagi.append("RISK-ON = AUD lekko pozytywny")
        elif rezim_typ == "RISK-OFF":
            score -= 5
            flagi.append("RISK-OFF = AUD pod silna presja")
        eem_signal = rezim.get("eem_signal", 0)
        if eem_signal == 1:
            score += 3
            flagi.append("EEM rosnie = AUD bullish (rynki wschodzace popyt na surowce)")
        elif eem_signal == -1:
            score -= 3
            flagi.append("EEM spada = AUD bearish")
        if commodity_bias == 1:
            score += 2
            flagi.append("Ropa rosnie = AUD (surowce) wsparcie")
        elif commodity_bias == -1:
            score -= 2
            flagi.append("Ropa spada = AUD presja")
        if usd_kierunek in ["MOCNY", "UMIARKOWANIE MOCNY"]:
            score -= 2
            flagi.append("Mocny USD = presja na AUD")

    # --- CAD ---
    elif waluta == "CAD":
        commodity_bias = surowce_analiza.get("commodity_bias", 0)
        if commodity_bias == 1:
            score += 4
            flagi.append("Ropa rosnie = CAD (petrodolar) silne wsparcie")
        elif commodity_bias == -1:
            score -= 4
            flagi.append("Ropa spada = CAD pod presja (petrodolar)")
        if rezim_typ == "RISK-ON":
            score += 2
            flagi.append("RISK-ON = CAD pozytywny")
        elif rezim_typ == "RISK-OFF":
            score -= 3
            flagi.append("RISK-OFF = CAD pod presja")
        eem_signal = rezim.get("eem_signal", 0)
        if eem_signal == 1:
            score += 2
            flagi.append("EEM rosnie = globalny apetyt na surowce - wspiera CAD")
        if usd_kierunek in ["MOCNY", "UMIARKOWANIE MOCNY"]:
            score -= 2
            flagi.append("Mocny USD = presja na CAD")

    # --- GOLD ---
    elif waluta == "GOLD":
        gld_zmiana = oblicz_zmiane_pct(dane_etf.get("GLD"), OKRES_SREDNI)
        if gld_zmiana is not None:
            if gld_zmiana > 1.0:
                score += 5
                flagi.append(f"GLD rosnie silnie ({gld_zmiana:+.2f}%) - GOLD bullish")
            elif gld_zmiana > 0.3:
                score += 2
                flagi.append(f"GLD rosnie ({gld_zmiana:+.2f}%) - GOLD lekko bullish")
            elif gld_zmiana < -1.0:
                score -= 5
                flagi.append(f"GLD spada silnie ({gld_zmiana:+.2f}%) - GOLD bearish")
            elif gld_zmiana < -0.3:
                score -= 2
                flagi.append(f"GLD spada ({gld_zmiana:+.2f}%) - GOLD lekko bearish")
        if rezim_typ == "RISK-OFF" and sila_rezimu >= 2:
            score += 4
            flagi.append("RISK-OFF silny = GOLD jako bezpieczna przystani")
        elif rezim_typ == "RISK-ON":
            score -= 2
            flagi.append("RISK-ON = GOLD pod presja (apetyt na ryzyko)")
        tlt_signal = rezim.get("tlt_signal", 0)
        if tlt_signal == -1 and (gld_zmiana is not None and gld_zmiana > 0):
            dywergencja = True
            score -= 2
            flagi.append("DYWERGENCJA: TLT spada ale GLD rosnie - sprzeczne sygnaly safe-haven")

    # --- SILVER ---
    elif waluta == "SILVER":
        gld_zmiana = oblicz_zmiane_pct(dane_etf.get("GLD"), OKRES_SREDNI)
        commodity_bias = surowce_analiza.get("commodity_bias", 0)
        if rezim_typ == "RISK-ON":
            score += 3
            flagi.append("RISK-ON = SILVER wspierany (metal przemyslowy)")
        elif rezim_typ == "RISK-OFF" and sila_rezimu >= 3:
            score += 2
            flagi.append("RISK-OFF silny = SILVER safe-haven (sladowy za GOLD)")
        elif rezim_typ == "RISK-OFF":
            score -= 1
            flagi.append("RISK-OFF - SILVER mieszane (metal przemyslowy + safe haven)")
        if commodity_bias == 1:
            score += 2
            flagi.append("Surowce rosna = SILVER wsparcie przemyslowe")
        elif commodity_bias == -1:
            score -= 2
            flagi.append("Surowce spadaja = SILVER presja")

    # --- Korekta score do zakresu 0-20 ---
    score = max(0, min(20, score))

    return {
        "score":       score,
        "flagi":       flagi,
        "dywergencja": dywergencja
    }


# =============================================================================
# GLOWNA FUNKCJA ANALIZY FLOW
# =============================================================================

def analizuj_flow():
    """
    Glowna funkcja Layer 3.
    Pobiera dane ETF, wykrywa rezim, oblicza score per waluta.

    Zwraca slownik z wynikami dla wszystkich walut + meta info.
    """

    print("\n" + "=" * 60)
    print("LAYER 3: INTERMARKET FLOW ENGINE")
    print("=" * 60)
    print("Pobieranie danych ETF przez yfinance...")

    # --- Pobierz dane dla wszystkich ETF ---
    dane_etf = {}
    for ticker in ETF_LISTA:
        print(f"  Pobieranie: {ticker} ({ETF_LISTA[ticker]})")
        dane_etf[ticker] = pobierz_dane_etf(ticker)

    # --- Wykryj rezim rynkowy ---
    print("\nAnaliza rezimu RISK-ON / RISK-OFF...")
    rezim = wykryj_rezim_rynkowy(dane_etf)

    print(f"  Rezim:             {rezim['rezim']}")
    print(f"  Sila:              {rezim['sila']}/4 potwierdzen")
    print(f"  Risk-ON:           {rezim['potwierdzenia_risk_on']} sygnaly")
    print(f"  Risk-OFF:          {rezim['potwierdzenia_risk_off']} sygnaly")
    for opis in rezim["opis"]:
        print(f"  >> {opis}")

    # --- Analiza dolara ---
    print("\nAnaliza sily dolara (UUP)...")
    usd_analiza = analizuj_dolar(dane_etf)
    print(f"  USD:               {usd_analiza['kierunek']} ({usd_analiza['zmiana']:+.2f}%)")

    # --- Analiza surowcow ---
    print("\nAnaliza surowcow (USO - ropa)...")
    surowce_analiza = analizuj_ropy_i_surowce(dane_etf)
    print(f"  Ropa (USO):        {surowce_analiza['kierunek']} ({surowce_analiza['zmiana']:+.2f}%)")

    # --- Oblicz score per waluta ---
    waluty = ["EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "GOLD", "SILVER"]
    wyniki_walut = {}

    print("\nObliczanie Flow Score per waluta...")
    print("-" * 50)

    for waluta in waluty:
        wynik = oblicz_score_waluty(waluta, rezim, usd_analiza, surowce_analiza, dane_etf)
        wyniki_walut[waluta] = wynik

        dyw_tag = " [DYWERGENCJA]" if wynik["dywergencja"] else ""
        print(f"  {waluta:<8} Score: {wynik['score']:>2}/20{dyw_tag}")
        for flaga in wynik["flagi"]:
            print(f"           >> {flaga}")

    # --- Crypto (BTC) - yfinance BTC-USD ---
    crypto = {}
    btc_dane = pobierz_dane_etf("BTC-USD", dni=65)
    if btc_dane is not None and len(btc_dane) >= 5:
        try:
            close_ser = btc_dane["Close"] if "Close" in btc_dane.columns else btc_dane.iloc[:, 3]
            close = np.asarray(close_ser).flatten()
        except Exception:
            close = np.array([])
        btc_cena = float(close[-1]) if len(close) > 0 else 0
        zmiana_5d = oblicz_zmiane_pct(btc_dane, 5)
        zmiana_20d = oblicz_zmiane_pct(btc_dane, 20)
        btc_bias = oblicz_momentum_ma(btc_dane, 5, 20)
        if zmiana_5d is None:
            zmiana_5d = 0
        if zmiana_20d is None:
            zmiana_20d = 0
        if btc_bias == 1:
            btc_trend = "BULLISH"
        elif btc_bias == -1:
            btc_trend = "BEARISH"
        else:
            btc_trend = "NEUTRALNY"
        crypto = {
            "btc_cena":       round(btc_cena, 2),
            "btc_trend":      btc_trend,
            "btc_zmiana_5d":  round(zmiana_5d, 2) if zmiana_5d else 0,
            "btc_zmiana_20d": round(zmiana_20d, 2) if zmiana_20d else 0,
            "btc_bias":       btc_bias,
        }
        btc_score = 10 + (5 if btc_bias == 1 else (-5 if btc_bias == -1 else 0))
        btc_score = max(0, min(20, btc_score))
        wyniki_walut["BTC"] = {"score": btc_score, "flagi": [f"BTC {btc_trend} | 20d: {zmiana_20d:+.1f}%"], "dywergencja": False}
        print(f"  BTC      Score: {btc_score:>2}/20")
        print(f"           >> BTC {btc_trend} | ${btc_cena:,.0f} | 5d: {zmiana_5d:+.1f}% | 20d: {zmiana_20d:+.1f}%")

    # --- Podsumowanie ---
    print("\n" + "=" * 60)
    print("PODSUMOWANIE LAYER 3:")
    print(f"  Rezim:       {rezim['rezim']}")
    print(f"  USD:         {usd_analiza['kierunek']}")
    print(f"  Surowce:     {surowce_analiza['kierunek']}")
    print("=" * 60 + "\n")

    # --- Zbuduj wynik finalny ---
    wynik_finalny = {
        "score":           0,
        "rezim":           rezim["rezim"],
        "rezim_sila":      rezim["sila"],
        "risk_on_count":   rezim["potwierdzenia_risk_on"],
        "risk_off_count":  rezim["potwierdzenia_risk_off"],
        "usd_kierunek":    usd_analiza["kierunek"],
        "usd_zmiana":      usd_analiza["zmiana"],
        "surowce_kierunek": surowce_analiza["kierunek"],
        "surowce_bias":    surowce_analiza["commodity_bias"],
        "waluty":          wyniki_walut,
        "crypto":          crypto,
        "sygnaly_etf":     rezim["opis"],
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Ogolny score jako srednia z walut (pomocnicze)
    wszystkie_score = [wyniki_walut[w]["score"] for w in wyniki_walut]
    wynik_finalny["score"] = round(sum(wszystkie_score) / len(wszystkie_score), 1)

    return wynik_finalny


def pobierz_score_dla_waluty(waluta, wynik_flow=None):
    """
    Helper - pobiera score dla konkretnej waluty z wyniku flow.
    Jesli wynik_flow jest None, uruchamia pelna analize.
    Uzywane przez main.py do integracji z systemem scoringu.
    """
    if wynik_flow is None:
        wynik_flow = analizuj_flow()
    waluty_map = wynik_flow.get("waluty", {})
    wynik = waluty_map.get(waluta.upper(), {})
    return wynik.get("score", 10)  # domyslnie 10 (neutralny) jesli brak danych


# =============================================================================
# FORMATOWANIE DO RAPORTU
# =============================================================================

def formatuj_flow_raport(wynik_flow):
    """
    Formatuje wyniki Layer 3 do czytelnego raportu tekstowego.
    Uzywane przez main.py / telegram_bot.py.
    """
    linie = []
    linie.append("--- LAYER 3: INTERMARKET FLOW ---")
    linie.append(f"Rezim:    {wynik_flow.get('rezim', 'BRAK')} (sila: {wynik_flow.get('rezim_sila', 0)}/4)")
    linie.append(f"USD:      {wynik_flow.get('usd_kierunek', 'BRAK')} ({wynik_flow.get('usd_zmiana', 0):+.2f}%)")
    linie.append(f"Surowce:  {wynik_flow.get('surowce_kierunek', 'BRAK')}")
    linie.append(f"Risk-ON:  {wynik_flow.get('risk_on_count', 0)} | Risk-OFF: {wynik_flow.get('risk_off_count', 0)}")
    linie.append("")
    linie.append("Flow Score per waluta:")
    waluty = wynik_flow.get("waluty", {})
    for waluta, wynik in waluty.items():
        dyw = " [!DYWERGENCJA]" if wynik.get("dywergencja") else ""
        linie.append(f"  {waluta:<8} {wynik.get('score', 0):>2}/20{dyw}")
    linie.append("")
    linie.append("Sygnaly ETF:")
    for sygnal in wynik_flow.get("sygnaly_etf", []):
        linie.append(f"  >> {sygnal}")
    linie.append(f"  (dane: {wynik_flow.get('timestamp', 'brak')})")

    return "\n".join(linie)


# =============================================================================
# TEST MODULU
# =============================================================================

if __name__ == "__main__":
    print("TEST: flow_engine.py - Layer 3 Intermarket Flow Engine")
    print("COT is contextual, not predictive.")
    print()

    wynik = analizuj_flow()

    print("\nRAWY WYNIK (JSON-like):")
    print(f"  Rezim:          {wynik['rezim']}")
    print(f"  USD:            {wynik['usd_kierunek']}")
    print(f"  Surowce:        {wynik['surowce_kierunek']}")
    print(f"  Ogolny score:   {wynik['score']}/20")
    print()
    print(formatuj_flow_raport(wynik))