from datetime import datetime


def klasyfikuj_typ_setupu(cot, cykl, surprise, event_risk) -> str:
    """
    META TAG 2: TYPE
    Okresla typ setupu transakcyjnego.

    EVENT       - transakcja wokol waznego wydarzenia makro
    CORRECTION  - korekta w glownym trendzie instytucjonalnym
    LATE CYCLE  - pozna faza cyklu, odwrocenie trendu
    RANGE RV    - powrot do sredniej w konsolidacji
    """
    faza       = cykl.get("phase", "UNKNOWN")
    zegar      = cykl.get("clock", "UNKNOWN")
    dojrzalosc = cykl.get("maturity", "UNKNOWN")
    high_events = event_risk.get("high_count", 0)
    surprise_4w = surprise.get("surprise_4w", 0)
    momentum    = cot.get("momentum", "MIXED")

    # EVENT - jest wazne wydarzenie w ciagu 48h
    if high_events >= 1:
        return "EVENT"

    # LATE CYCLE - pozna faza z odwracaniem
    if dojrzalosc == "LATE" and faza in ["SLOWDOWN", "CONTRACTION"]:
        return "LATE CYCLE RV"

    # CORRECTION - silny momentum COT ale zegar przeciwny
    if momentum in ["BULLISH", "BEARISH"] and abs(surprise_4w) < 0.3:
        return "CORRECTION"

    # RANGE RV - slaby momentum, stabilny surprise
    if momentum == "MIXED" and abs(surprise_4w) < 0.5:
        return "RANGE RV"

    return "CORRECTION"


def klasyfikuj_horyzont(cykl, cot, scoring) -> str:
    """
    META TAG 3: HORIZON
    Okresla optymalny horyzont czasowy transakcji.

    1w  - 1 tydzien (dane kratkookresowe dominuja)
    2w  - 2 tygodnie (momentum COT)
    4w  - 4 tygodnie (standardowy swing)
    8w  - 8 tygodni (pozycja strukturalna)
    """
    faza       = cykl.get("phase", "UNKNOWN")
    dojrzalosc = cykl.get("maturity", "UNKNOWN")
    zscore_cot = abs(cot.get("zscore", 0))
    conviction  = scoring.get("conviction", "PASS")

    # Pozna faza - krotszy horyzont (moze sie odwrocic)
    if dojrzalosc == "LATE":
        return "1-2w"

    # Wysoki conviction + wczesna faza = dluzszy horyzont
    if conviction == "WYSOKI" and dojrzalosc == "EARLY":
        if faza in ["EXPANSION", "RECOVERY"]:
            return "4-8w"

    # Umiarkowany = standardowy swing
    if conviction == "UMIARKOWANY":
        return "2-4w"

    # Ekstremum COT = krotszy horyzont
    if zscore_cot > 1.5:
        return "1-2w"

    return "2-4w"


def generuj_meta_tagi(instrument, cot, cykl, surprise, event_risk, scoring) -> dict:
    """
    Glowna funkcja - generuje wszystkie 3 META TAGI
    dla danego instrumentu.
    """

    # META TAG 1: BIAS
    bias = scoring.get("bias", "CZEKAJ")
    if bias == "KUP":
        meta_bias = "BUY"
    elif bias == "SPRZEDAJ":
        meta_bias = "SELL"
    else:
        meta_bias = "NEUTRAL"

    # META TAG 2: TYPE
    meta_type = klasyfikuj_typ_setupu(cot, cykl, surprise, event_risk)

    # META TAG 3: HORIZON
    meta_horizon = klasyfikuj_horyzont(cykl, cot, scoring)

    # Wariant analizy (jak w NIL - 2 warianty)
    lacznie = scoring.get("lacznie", 0)
    if meta_bias != "NEUTRAL" and lacznie >= 45:
        wariant_a = f"{meta_bias} {instrument} - trend following"
        wariant_b = f"Czekaj na korekte do wejscia w {meta_bias}"
    else:
        wariant_a = f"Obserwuj {instrument} - brak sygnalu"
        wariant_b = f"Nastepna okazja przy zmianie momentum COT"

    return {
        "instrument":  instrument,
        "meta_bias":   meta_bias,
        "meta_type":   meta_type,
        "meta_horizon": meta_horizon,
        "wariant_a":   wariant_a,
        "wariant_b":   wariant_b,
        "conviction":  scoring.get("conviction", "PASS"),
        "score":       lacznie,
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def drukuj_karte(meta: dict, cot: dict, cykl: dict, makro: dict):
    """
    Drukuje karte transakcyjna w formacie NIL.
    To jest finalny output agenta.
    """
    bias_ikona = "[+] BUY" if meta["meta_bias"] == "BUY" else \
                 "[-] SELL" if meta["meta_bias"] == "SELL" else \
                 "⚪ NEUTRAL"

    print(f"""
╔══════════════════════════════════════════════════╗
  {meta['instrument']}  |  Score: {meta['score']}/80  |  {meta['conviction']}
══════════════════════════════════════════════════
  BIAS:    {bias_ikona}
  TYPE:    {meta['meta_type']}
  HORIZON: {meta['meta_horizon']}
──────────────────────────────────────────────────
  FAZA:    {cykl.get('phase','?')} | ZEGAR: {cykl.get('clock','?')}
  CLI:     {cykl.get('cli_momentum','?')}
  COT:     {cot.get('momentum','?')} | Z-score: {cot.get('zscore',0)}
  Net Pos: {cot.get('net_position',0):,} kontraktow
──────────────────────────────────────────────────
  WARIANT A: {meta['wariant_a']}
  WARIANT B: {meta['wariant_b']}
──────────────────────────────────────────────────
  DXY:    {makro.get('DXY',{}).get('value','?')} ({makro.get('DXY',{}).get('trend','?')})
  US10Y:  {makro.get('US10Y',{}).get('value','?')}%
  Curve:  {makro.get('YIELD_CURVE','?')}
╚══════════════════════════════════════════════════╝""")


if __name__ == "__main__":
    # Test modulu
    print("meta_engine.py - gotowy do integracji z main.py")
    print("3 META TAGI: BIAS | TYPE | HORIZON")
    print("Uruchom py main.py zeby zobaczyc pelny raport")