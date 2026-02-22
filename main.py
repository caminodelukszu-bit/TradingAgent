# =============================================================================
# main.py - Trading Agent v3.0
# Layer 1: COT           (cot_engine.py)
# Layer 2: Market Regime (cycle_engine.py + regime_engine.py + macro_engine.py)
# Layer 3: Intermarket   (flow_engine.py)
# Layer 4a: Surprise    (surprise_engine.py - zaskoczenia makro)
# Layer 4b: Sentiment   (sentiment_engine.py - retail kontrarianski, MyFXBook)
# Layer 5: News/Tech    (news_engine.py - tymczasowo)
# Layer 6: Risk/Events   (event_calendar.py)
# Risk/Portfolio:        (risk_engine.py - ekspozycja, max pozycje)
# Uczenie:               (outcome_tracker + feedback_analyzer - co dziala/nie; commentary_engine - komentarz)
# Sytuacje + Workflow:   (situation_engine - zmienne->sytuacja; workflow_engine - co i jak dlugo handlowac)
# =============================================================================

from cot_engine      import analyze_cot
from macro_engine    import analyze_macro
from cycle_engine    import get_cycle_phase
from surprise_engine  import analyze_surprise
from sentiment_engine import get_outlook_cache, analyze_sentiment
from event_calendar   import analyze_event_risk, get_upcoming_events_summary
from meta_engine     import generuj_meta_tagi, drukuj_karte
from news_engine     import analyze_news
from flow_engine     import analizuj_flow
from regime_engine   import analizuj_wszystkie_rezimy
from risk_engine       import oblicz_ryzyko_portfela
from outcome_tracker   import (
    save_signals, update_outcomes, get_verified, get_aggregated_feedback,
    get_conviction_aggregation, get_event_risk_aggregation, get_similar_signals,
    get_verified_by_horizon, get_user_feedback_aggregation,
)
from commentary_engine import generate as generuj_komentarz
from situation_engine  import definiuj_sytuacje
from feedback_analyzer import analyze_feedback, apply_learned_conviction
from workflow_engine   import build_workflow
from instruction_engine import build_instruction, get_primary_driver, build_rationale
from datetime          import datetime

try:
    from desk_controller import run_desk_cycle
except ImportError:
    run_desk_cycle = None

try:
    from rag_store import add_report as rag_add_report, add_feedback as rag_add_feedback, add_outcomes as rag_add_outcomes, add_claude_insight as rag_add_claude_insight
except ImportError:
    rag_add_report = rag_add_feedback = rag_add_outcomes = rag_add_claude_insight = None

try:
    from money_net_engine import get_global_yields as money_net_get_global_yields
except ImportError:
    money_net_get_global_yields = None

INSTRUMENTY = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "GOLD", "SILVER", "BTC"]
WALUTY_FX   = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF"]
WALUTY_NEWS = ["EUR", "GBP", "JPY", "AUD", "CAD", "GOLD", "OIL", "BTC"]

MAX_SCORE_RAW = 120

# =============================================================================
# GRUPY KORELACYJNE - zapobiega parom o tej samej ekspozycji
# =============================================================================

GRUPY_KORELACYJNE = {
    "SUROWCE":    ["AUD", "CAD"],
    "SAFE_HAVEN": ["JPY", "CHF"],
    "METALE":     ["GOLD", "SILVER"],
    "EUROPA":     ["EUR", "GBP", "CHF"],
    "CRYPTO":     ["BTC"],
}

# Built-in risk disclosure (spec instytucjonalna – dlaczego system może nie działać)
RISK_DISCLOSURE = (
    "1) Lag COT (dane z wtorku). 2) Nagłe zmiany makro. 3) Instytucje uśredniają pozycje. "
    "4) Fałszywy flip bez kontynuacji. 5) Range regime mimo momentum. "
    "6) Hedge distortion (Commercials). 7) Brak płynności przy ekstremach. "
    "COT is contextual, not predictive."
)

# Pary lustrzane (ujemna korelacja): gdy oba sygnaly w tym samym kierunku = potwierdzenie +10 sily
PARY_LUSTRIANE = [("EUR", "CHF"), ("AUD", "CAD"), ("GBP", "CHF")]

# Cross: nie laczymy metalow z walutami FX ani BTC z walutami (tylko vs USD)
PARY_WYKLUCZONE = [
    "GOLD/SILVER", "SILVER/GOLD",
    "AUD/GOLD", "CAD/GOLD", "EUR/GOLD", "GBP/GOLD", "JPY/GOLD", "CHF/GOLD", "BTC/GOLD",
    "GOLD/AUD", "GOLD/CAD", "GOLD/EUR", "GOLD/GBP", "GOLD/JPY", "GOLD/CHF", "GOLD/BTC",
    "AUD/SILVER", "CAD/SILVER", "EUR/SILVER", "GBP/SILVER", "JPY/SILVER", "CHF/SILVER", "BTC/SILVER",
    "SILVER/AUD", "SILVER/CAD", "SILVER/EUR", "SILVER/GBP", "SILVER/JPY", "SILVER/CHF", "SILVER/BTC",
    "AUD/BTC", "CAD/BTC", "EUR/BTC", "GBP/BTC", "JPY/BTC", "CHF/BTC",
    "BTC/AUD", "BTC/CAD", "BTC/EUR", "BTC/GBP", "BTC/JPY", "BTC/CHF",
]

# =============================================================================
# SCORING - 6 WARSTW
# =============================================================================

def oblicz_scoring(cot, makro, cykl, surprise, event_risk,
                   news=None, flow=None, sentiment=None,
                   regime_score_tech=10, kara_range=0) -> dict:

    cot_score       = cot.get("score", 0)
    cykl_score      = cykl.get("score", 0)
    flow_score      = flow.get("score", 10) if flow else 10
    surprise_score  = surprise.get("score", 0)
    sentiment_score = sentiment.get("score", 0) if sentiment else 0
    news_score      = news.get("score", 0) if news else 0
    makro_score     = makro.get("macro_score", 0)

    # Layer 2 = cykl ekonomiczny 40% + rezim techniczny 40% + makro 20%
    layer2_score = min(20, round(
        cykl_score * 0.4 + regime_score_tech * 0.6 + makro_score * 0.2
    ))

    raw = cot_score + layer2_score + flow_score + surprise_score + sentiment_score + news_score

    # --- Kary ---
    kara = event_risk.get("penalty", 0)
    if kara < 0:
        print(f"   Kara eventowa: {kara} pkt ({event_risk.get('risk_level')})")

    if cot.get("extreme_warning"):
        kara -= 10
        print("   Kara COT ekstremum: -10 pkt")

    if kara_range < 0:
        kara += kara_range
        print(f"   Kara RANGE regime: {kara_range} pkt")

    bias_cot = cot.get("bias", "NEUTRAL")
    if bias_cot == "BUY" and flow_score < 6:
        kara -= 5
        print("   Kara dywergencja COT-FLOW: -5 pkt")
    elif bias_cot == "SELL" and flow_score > 14:
        kara -= 5
        print("   Kara dywergencja COT-FLOW: -5 pkt")

    raw_po_karach = raw + kara
    lacznie = round((raw_po_karach / MAX_SCORE_RAW) * 100)
    lacznie = max(0, min(100, lacznie))

    if lacznie >= 80:
        conviction = "WYSOKI"
    elif lacznie >= 55:
        conviction = "UMIARKOWANY"
    elif lacznie >= 35:
        conviction = "NISKI"
    else:
        conviction = "PASS"

    bias_surprise  = surprise.get("bias", "NEUTRALNY")
    bias_sentiment = sentiment.get("bias", "NEUTRALNY") if sentiment else "NEUTRALNY"
    bias_cykl      = cykl.get("phase", "UNKNOWN")
    bias_news      = news.get("bias", "NEUTRALNY") if news else "NEUTRALNY"
    flow_rezim     = flow.get("rezim", "NEUTRALNY") if flow else "NEUTRALNY"

    buy_sygnaly = sum([
        1 if bias_cot      == "BUY"       else 0,
        1 if bias_surprise == "POZYTYWNY" else 0,
        1 if bias_sentiment == "BUY"      else 0,
        1 if bias_cykl in ["EXPANSION", "RECOVERY"] else 0,
        1 if bias_news     == "POZYTYWNY" else 0,
        1 if flow_rezim    == "RISK-ON" and bias_cot != "SELL" else 0,
    ])
    sell_sygnaly = sum([
        1 if bias_cot      == "SELL"      else 0,
        1 if bias_surprise == "NEGATYWNY" else 0,
        1 if bias_sentiment == "SELL"     else 0,
        1 if bias_cykl in ["CONTRACTION", "SLOWDOWN"] else 0,
        1 if bias_news     == "NEGATYWNY" else 0,
        1 if flow_rezim    == "RISK-OFF" and bias_cot != "BUY" else 0,
    ])

    if buy_sygnaly >= 2 and conviction != "PASS":
        bias = "KUP"
    elif sell_sygnaly >= 2 and conviction != "PASS":
        bias = "SPRZEDAJ"
    else:
        bias = "CZEKAJ"

    return {
        "lacznie":      lacznie,
        "conviction":   conviction,
        "bias":         bias,
        "cot":          cot_score,
        "cykl":         layer2_score,
        "flow":         flow_score,
        "surprise":     surprise_score,
        "sentiment":    sentiment_score,
        "news":         news_score,
        "kara":         kara,
        "raw":          raw,
        "buy_sygnaly":  buy_sygnaly,
        "sell_sygnaly": sell_sygnaly,
    }


# =============================================================================
# PARY WALUTOWE - CROSS
# =============================================================================

def czy_ta_sama_korelacja(a, b):
    for _, waluty in GRUPY_KORELACYJNE.items():
        if a in waluty and b in waluty:
            return True
    return False


def generuj_pary_walutowe(wyniki):
    pary = []
    for i, wa in enumerate(wyniki):
        for j, wb in enumerate(wyniki):
            if i >= j:
                continue
            ia, ib = wa["instrument"], wb["instrument"]
            if ia + "/" + ib in PARY_WYKLUCZONE or ib + "/" + ia in PARY_WYKLUCZONE:
                continue
            if czy_ta_sama_korelacja(ia, ib):
                if wa["bias"] == wb["bias"] and wa["bias"] in ["KUP", "SPRZEDAJ"]:
                    continue

            sa, sb  = wa["lacznie"], wb["lacznie"]
            roznica = abs(sa - sb)
            if roznica < 10:
                continue

            if sa > sb:
                mocna, slaba = ia, ib
                sm, ss       = sa, sb
                bm, bs       = wa["bias"], wb["bias"]
                cm, cs       = wa["conviction"], wb["conviction"]
            else:
                mocna, slaba = ib, ia
                sm, ss       = sb, sa
                bm, bs       = wb["bias"], wa["bias"]
                cm, cs       = wb["conviction"], wa["conviction"]

            if bm == "KUP" and bs == "SPRZEDAJ":
                sila = roznica + 20
                typ  = "TREND FOLLOWING"
            elif bm == "KUP" and bs == "CZEKAJ":
                sila = roznica + 5
                typ  = "MOMENTUM"
            elif bm == "CZEKAJ" and bs == "SPRZEDAJ":
                sila = roznica + 5
                typ  = "MOMENTUM"
            else:
                sila = roznica - 5
                typ  = "OBSERWACJA"

            rk = {"WYSOKI": 3, "UMIARKOWANY": 2, "NISKI": 1, "PASS": 0}
            rm = {3: "WYSOKI", 2: "UMIARKOWANY", 1: "NISKI", 0: "PASS"}
            conv = rm[min(rk.get(cm, 0), rk.get(cs, 0))]

            if conv == "PASS" or sila < 10:
                continue

            ryzyko = "2% kapitalu" if conv == "WYSOKI" else (
                     "1% kapitalu" if conv == "UMIARKOWANY" else "0.5% kapitalu")

            ea = wa.get("event_risk", "NISKI")
            eb = wb.get("event_risk", "NISKI")
            ev = ""
            if ea in ["WYSOKI", "KRYTYCZNY"] or eb in ["WYSOKI", "KRYTYCZNY"]:
                ev   = "UWAGA: event risk!"
                sila = round(sila * 0.7)

            pary.append({
                "para": mocna + "/" + slaba,
                "waluta_mocna": mocna, "waluta_slaba": slaba,
                "score_mocna": sm, "score_slaba": ss,
                "sila_sygnalu": sila, "typ_sygnalu": typ,
                "conviction": conv, "ryzyko": ryzyko,
                "event_alert": ev, "bias_mocna": bm, "bias_slaba": bs,
            })

    pary.sort(key=lambda x: x["sila_sygnalu"], reverse=True)
    return pary


# =============================================================================
# PARY VS USD
# =============================================================================

def generuj_pary_vs_usd(wyniki, flow_globalny):
    usd_kier = flow_globalny.get("usd_kierunek", "NEUTRALNY") if flow_globalny else "NEUTRALNY"

    usd_map = {
        "MOCNY":              (65, "KUP"),
        "UMIARKOWANIE MOCNY": (55, "KUP"),
        "SLABY":              (35, "SPRZEDAJ"),
        "UMIARKOWANIE SLABY": (45, "SPRZEDAJ"),
    }
    usd_score, usd_bias = usd_map.get(usd_kier, (50, "CZEKAJ"))

    pary = []
    for w in wyniki:
        inst = w["instrument"]
        nazwa = {"GOLD": "XAU/USD", "SILVER": "XAG/USD", "BTC": "BTC/USD (USDT)"}.get(inst, inst + "/USD")

        si    = w["lacznie"]
        bi    = w["bias"]
        ci    = w.get("learned_conviction") or w["conviction"]
        rezim = w.get("typ_rezimu", "NEUTRALNY")

        # GOLD i SILVER: kierunek z rezimu technicznego (40EMA + ATR), nie ze score (score moze byc niski przez kary eventowe)
        if inst in ["GOLD", "SILVER"]:
            if "BULLISH" in rezim:
                kier = "LONG"
                sila = 20 + (10 if "TRENDING" in rezim else 5)
                typ  = "TREND FOLLOWING"
                rozn = abs(si - usd_score)
            elif "BEARISH" in rezim:
                kier = "SHORT"
                sila = 20 + (10 if "TRENDING" in rezim else 5)
                typ  = "TREND FOLLOWING"
                rozn = abs(si - usd_score)
            else:
                continue  # RANGE - pomijamy GOLD/SILVER vs USD gdy brak trendu
            if w.get("event_risk") in ["WYSOKI", "KRYTYCZNY"]:
                sila = round(sila * 0.7)
            cp = "UMIARKOWANY" if "TRENDING" in rezim else "NISKI"
            cp = w.get("learned_conviction") or cp
            ry = "1% kapitalu" if cp == "UMIARKOWANY" else "0.5% kapitalu"
            ev = "UWAGA: event risk!" if w.get("event_risk") in ["WYSOKI", "KRYTYCZNY"] else ""
            pary.append({
                "para": nazwa, "kierunek": kier,
                "score_inst": si, "score_usd": usd_score,
                "usd_kierunek": usd_kier, "roznica": rozn,
                "sila_sygnalu": sila, "typ_sygnalu": typ,
                "conviction": cp, "ryzyko": ry,
                "event_alert": ev, "bias_inst": bi, "usd_bias": usd_bias,
                "situation_type": w.get("situation_id", ""),
            })
            continue

        rozn = abs(si - usd_score)
        if rozn < 5:
            continue
        if ci == "PASS" and rozn < 15:
            continue

        if si > usd_score:
            kier = "LONG"
            sila = rozn + (15 if bi == "KUP" and usd_bias == "SPRZEDAJ" else 5)
            typ  = "TREND FOLLOWING" if bi == "KUP" else "MOMENTUM"
        else:
            kier = "SHORT"
            sila = rozn + (15 if bi == "SPRZEDAJ" and usd_bias == "KUP" else 5)
            typ  = "TREND FOLLOWING" if bi == "SPRZEDAJ" else "MOMENTUM"

        if ci == "WYSOKI" and rozn >= 25:
            cp = "WYSOKI"
            ry = "2% kapitalu"
        elif ci in ["WYSOKI", "UMIARKOWANY"] and rozn >= 15:
            cp = "UMIARKOWANY"
            ry = "1% kapitalu"
        else:
            cp = "NISKI"
            ry = "0.5% kapitalu"

        ev = ""
        if w.get("event_risk") in ["WYSOKI", "KRYTYCZNY"]:
            ev   = "UWAGA: event risk!"
            sila = round(sila * 0.7)
            cp   = "NISKI"

        pary.append({
            "para": nazwa, "kierunek": kier,
            "score_inst": si, "score_usd": usd_score,
            "usd_kierunek": usd_kier, "roznica": rozn,
            "sila_sygnalu": sila, "typ_sygnalu": typ,
            "conviction": cp, "ryzyko": ry,
            "event_alert": ev, "bias_inst": bi, "usd_bias": usd_bias,
            "situation_type": w.get("situation_id", ""),
        })

    # Bonus za lustrzane potwierdzenie (np. EUR/USD LONG + CHF/USD LONG = oba USD weak)
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}
    for p in pary:
        p["lustrzane_potwierdzenie"] = False
        inst = nazwa_do_inst.get(p["para"], p["para"].split("/")[0] if "/" in p["para"] else p["para"])
        for a, b in PARY_LUSTRIANE:
            if inst != a and inst != b:
                continue
            other = b if inst == a else a
            other_para = {"GOLD": "XAU/USD", "SILVER": "XAG/USD", "BTC": "BTC/USD (USDT)"}.get(other, other + "/USD")
            for p2 in pary:
                if p2 is p:
                    continue
                inst2 = nazwa_do_inst.get(p2["para"], p2["para"].split("/")[0] if "/" in p2["para"] else "")
                if inst2 == other and p2["kierunek"] == p["kierunek"]:
                    p["sila_sygnalu"] += 10
                    p["lustrzane_potwierdzenie"] = True
                    break
            if p.get("lustrzane_potwierdzenie"):
                break

    pary.sort(key=lambda x: x["sila_sygnalu"], reverse=True)
    return pary


# =============================================================================
# DRUKOWANIE TABELI PAR
# =============================================================================

def drukuj_tabele_par(pary_cross, pary_usd):
    S = "=" * 78
    print("\n" + S)
    print("PARY DO HANDLU - CROSS (waluta vs waluta):")
    print(S)
    if not pary_cross:
        print("  Brak wyraznych sygnalow cross.")
    else:
        print("  PARA            SILA   CONVICTION     TYP                    RYZYKO")
        print("  " + "-" * 74)
        for p in pary_cross[:8]:
            ev = " [!EVENT]" if p["event_alert"] else ""
            print(f"  {p['para']:<15} {p['sila_sygnalu']:<7} {p['conviction']:<14} {p['typ_sygnalu']:<22} {p['ryzyko']}{ev}")
            print(f"  {'':15} Mocna: {p['waluta_mocna']} ({p['score_mocna']}/100 {p['bias_mocna']}) | Slaba: {p['waluta_slaba']} ({p['score_slaba']}/100 {p['bias_slaba']})")

    print("\n" + S)
    usd_info = pary_usd[0]["usd_kierunek"] if pary_usd else "NEUTRALNY"
    print(f"PARY DO HANDLU - vs USD  (USD: {usd_info}):")
    print(S)
    if not pary_usd:
        print("  USD neutralny - brak wyraznych sygnalow vs USD.")
    else:
        print("  PARA            KIER.   SILA   CONVICTION     TYP                    RYZYKO")
        print("  " + "-" * 74)
        for p in pary_usd[:10]:
            ev = " [!EVENT]" if p["event_alert"] else ""
            lz = " [LUSTRZANE]" if p.get("lustrzane_potwierdzenie") else ""
            inst = p["para"].split("/")[0]
            print(f"  {p['para']:<15} {p['kierunek']:<8}{p['sila_sygnalu']:<7} {p['conviction']:<14} {p['typ_sygnalu']:<22} {p['ryzyko']}{ev}{lz}")
            print(f"  {'':15} {inst}: {p['score_inst']}/100 (bias:{p['bias_inst']}) | USD: {p['score_usd']}/100 ({p['usd_kierunek']})")

    print()
    print("  LEGENDA:")
    print("  LONG  = kupuj 1.walute sprzedaj 2.  | SHORT = sprzedaj 1. kupuj 2.")
    print("  XAU/USD=zloto | XAG/USD=srebro | BTC/USD=Bitcoin (=BTC/USDT)")
    print("  Sila: >50 mocny | 30-50 umiarkowany | <30 slaby | [!EVENT]=uwazaj")


# =============================================================================
# GLOWNA FUNKCJA
# =============================================================================

def generuj_raport(tryb: str = "STANDARDOWY"):
    S1 = "=" * 65
    S2 = "=" * 78

    print("\n" + S1)
    print(f"  SofikaMax Agent - RAPORT {tryb}")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(S1)

    # --- DANE GLOBALNE ---
    print("\n[1/6] Pobieram dane makroekonomiczne z FRED...")
    makro = analyze_macro()

    print("\n[2/6] Pobieram dane ETF - Layer 3 Intermarket Flow...")
    try:
        flow_globalny = analizuj_flow()
        flow_ok       = True
        print(f"      Rezim: {flow_globalny.get('rezim','?')} | USD: {flow_globalny.get('usd_kierunek','?')}")
        crypto_info   = flow_globalny.get("crypto", {})
        if crypto_info.get("btc_cena", 0) > 0:
            print(f"      BTC: ${crypto_info.get('btc_cena',0):,.0f} | {crypto_info.get('btc_trend','?')} | 20d: {crypto_info.get('btc_zmiana_20d',0):+.1f}%")
    except Exception as e:
        print(f"      BLAD flow_engine: {e}")
        flow_globalny = None
        flow_ok       = False

    print("\n[3/6] Pobieram dane Weekly - Layer 2 Regime Engine...")
    try:
        rezimy = analizuj_wszystkie_rezimy(INSTRUMENTY)
        regime_ok = True
        print("      Regime engine OK")
    except Exception as e:
        print(f"      BLAD regime_engine: {e}")
        rezimy    = {}
        regime_ok = False

    # --- Layer 4b: Retail Sentiment (jedno wywolanie API na wszystkie pary) ---
    print("\n[4b/6] Pobieram retail sentiment (MyFXBook)...")
    try:
        sentiment_cache = get_outlook_cache()
        sentiment_ok = bool(sentiment_cache)
        print("      Sentiment engine OK" if sentiment_ok else "      Brak danych (ustaw MYFXBOOK w config lub pomijam)")
    except Exception as e:
        print(f"      BLAD sentiment_engine: {e}")
        sentiment_cache = {}
        sentiment_ok = False

    wyniki = []

    # --- ANALIZA PER INSTRUMENT ---
    for instrument in INSTRUMENTY:
        print(f"\n{'─' * 50}")
        print(f"Analizuje: {instrument}")

        # === LAYER 1: COT (BTC nie ma danych COT - uzywamy flow) ===
        if instrument == "BTC":
            crypto_data  = flow_globalny.get("crypto", {}) if flow_ok and flow_globalny else {}
            btc_bias_raw = crypto_data.get("btc_bias", 0)
            btc_bias_str = "BUY" if btc_bias_raw == 1 else ("SELL" if btc_bias_raw == -1 else "NEUTRAL")
            btc_flow_sc  = flow_globalny.get("waluty", {}).get("BTC", {}).get("score", 10) if flow_ok and flow_globalny else 10
            cot = {
                "score":           btc_flow_sc,
                "bias":            btc_bias_str,
                "momentum":        crypto_data.get("btc_trend", "NEUTRALNY"),
                "zscore":          0,
                "net_position":    0,
                "extreme_warning": False,
            }
            print(f"[BTC] Score z flow: {btc_flow_sc}/20 | Bias: {btc_bias_str} | {crypto_data.get('btc_trend','?')} | ${crypto_data.get('btc_cena',0):,.0f}")
        else:
            print("[COT] Pobieranie danych instytucjonalnych...")
            cot = analyze_cot(instrument)

        # === LAYER 2: Cykl ekonomiczny ===
        if instrument in WALUTY_FX:
            print("[CYKL] Sprawdzanie fazy ekonomicznej...")
            cykl = get_cycle_phase(instrument)
        else:
            cykl = {"score": 10, "phase": "N/A", "clock": "N/A",
                    "cli": 0, "cli_slope": 0, "maturity": "N/A"}

        # === LAYER 2: Rezim techniczny (40EMA + HH/HL + ATR) ===
        if regime_ok and instrument in rezimy:
            rw                = rezimy[instrument]
            regime_score_tech = rw.get("score", 10)
            range_warning     = rw.get("range_warning", False)
            kara_range        = rw.get("kara_range", 0)
            typ_rezimu        = rw.get("typ_rezimu", "NEUTRALNY")
        else:
            regime_score_tech = 10
            range_warning     = False
            kara_range        = 0
            typ_rezimu        = "NIEZNANY"

        # === LAYER 3: Flow per waluta ===
        if flow_ok and flow_globalny:
            wf  = flow_globalny.get("waluty", {}).get(instrument.upper(), {})
            flow_per_waluta = {
                "score":        wf.get("score", 10),
                "rezim":        flow_globalny.get("rezim", "NEUTRALNY"),
                "usd_kierunek": flow_globalny.get("usd_kierunek", "NEUTRALNY"),
                "dywergencja":  wf.get("dywergencja", False),
            }
        else:
            flow_per_waluta = {"score": 10, "rezim": "NEUTRALNY", "dywergencja": False}

        # === LAYER 4a: Surprise (zaskoczenia makro) ===
        if instrument in WALUTY_FX:
            print("[SURPRISE] Analiza zaskoczen makro...")
            surprise = analyze_surprise(instrument)
        else:
            surprise = {"score": 5, "bias": "NEUTRALNY",
                        "momentum": "N/A", "surprise_4w": 0, "health": "N/A"}

        # === LAYER 4b: Sentiment (retail kontrarianski) ===
        sentiment = analyze_sentiment(instrument, sentiment_cache)
        if sentiment.get("poziom_retail_long") is not None:
            print(f"   [SENTIMENT] Retail long: {sentiment['poziom_retail_long']}% | Bias: {sentiment['bias']} | Score: {sentiment['score']}/20")
        elif sentiment.get("source") == "claude" and sentiment.get("rationale"):
            r = sentiment["rationale"][:60]
            print(f"   [SENTIMENT] Claude (news): {sentiment['bias']} | Score: {sentiment['score']}/20 | {r}{'...' if len(sentiment['rationale']) > 60 else ''}")

        # === LAYER 6: Event risk ===
        event_waluta = instrument if instrument in WALUTY_FX else "USD"
        event_risk   = analyze_event_risk(currency=event_waluta, days_ahead=7)

        # GOLD / SILVER / BTC maja wlasny trend - kara eventowa max -10 (nie -20)
        if instrument in ["GOLD", "SILVER", "BTC"]:
            if event_risk.get("penalty", 0) < -10:
                event_risk = dict(event_risk)
                event_risk["penalty"] = -10
                print(f"   [INFO] {instrument}: kara eventowa ograniczona do -10 pkt")

        # === LAYER 5: News ===
        print("[NEWS] Analiza sentymentu...")
        news = analyze_news(instrument if instrument in WALUTY_NEWS else "USD")

        # === SCORING FINALNY ===
        scoring = oblicz_scoring(
            cot, makro, cykl, surprise, event_risk,
            news=news, flow=flow_per_waluta, sentiment=sentiment,
            regime_score_tech=regime_score_tech, kara_range=kara_range
        )
        # Sytuacja = połączenie zmiennych z wszystkich modułów (podstawa pod META TAGI i warianty)
        sit = definiuj_sytuacje(
            cot, cykl, surprise, event_risk,
            regime_type=typ_rezimu,
            range_warning=range_warning,
            flow_rezim=flow_per_waluta.get("rezim"),
            flow_score=flow_per_waluta.get("score", 10),
            flow_dywergencja=flow_per_waluta.get("dywergencja", False),
            scoring=scoring,
        )
        meta = generuj_meta_tagi(instrument, cot, cykl, surprise, event_risk, scoring)

        wyniki.append({
            "instrument":    instrument,
            "situation_id": sit["situation_id"],
            "situation_label": sit["situation_label"],
            "bias":          scoring["bias"],
            "lacznie":       scoring["lacznie"],
            "conviction":    scoring["conviction"],
            "cot_bias":      cot.get("bias", "?"),
            "faza":          cykl.get("phase", "N/A"),
            "zegar":         cykl.get("clock", "N/A"),
            "zscore_cot":    cot.get("zscore", 0),
            "net_pos":       cot.get("net_position", 0),
            "surprise_4w":   surprise.get("surprise_4w", 0),
            "sentiment":     sentiment.get("score", 0),
            "retail_long":   sentiment.get("poziom_retail_long"),
            "event_risk":    event_risk.get("risk_level", "NISKI"),
            "event_high_count": event_risk.get("high_count", 0),
            "news_bias":     news.get("bias", "NEUTRALNY"),
            "news_nps":      news.get("nps", 0),
            "top_news":      news.get("top_news", ""),
            "flow_score":    flow_per_waluta.get("score", 10),
            "flow_rezim":    flow_per_waluta.get("rezim", "NEUTRALNY"),
            "flow_dyw":      flow_per_waluta.get("dywergencja", False),
            "typ_rezimu":    typ_rezimu,
            "range_warning": range_warning,
            "meta_bias":     meta["meta_bias"],
            "meta_type":     meta["meta_type"],
            "meta_horizon":  meta["meta_horizon"],
            "wariant_a":     meta["wariant_a"],
            "wariant_b":     meta["wariant_b"],
            "szczegoly":     scoring,
            "cot_obj":       cot,
            "cykl_obj":      cykl,
        })

    wyniki.sort(key=lambda x: x["lacznie"], reverse=True)

    # ── TABELA GLOWNA ─────────────────────────────────────────
    print("\n\n" + S2)
    print(f"{'SCORING PER WALUTA':^78}")
    print(S2)
    print("WALUTA   BIAS         SCORE      CONVICTION      REZIM                   FLOW   HORIZON")
    print("-" * 78)
    for w in wyniki:
        ikona = "BUY " if w["meta_bias"] == "BUY" else ("SELL" if w["meta_bias"] == "SELL" else "    ")
        rng   = "[R]" if w["range_warning"] else "   "
        print(
            f"{ikona} {w['instrument']:<6} "
            f"{w['bias']:<12} "
            f"{w['lacznie']}/100  "
            f"{w['conviction']:<15} "
            f"{w['typ_rezimu']:<22}  "
            f"{w['flow_score']}/20 "
            f"{rng} {w['meta_horizon']}"
        )

    # ── UCZENIE: weryfikacja, feedback, learned conviction (save_signals po wygenerowaniu par) ─
    report_date = datetime.now().strftime("%Y-%m-%d")
    verified = get_verified(limit=10)
    aggregated = get_aggregated_feedback(min_samples=2)
    feedback = analyze_feedback(aggregated) if aggregated else {}
    for w in wyniki:
        w["learned_conviction"] = apply_learned_conviction(
            w["conviction"],
            w.get("situation_id", "OTHER"),
            feedback.get("situation_types_low", []),
        )

    # ── PARY WALUTOWE ─────────────────────────────────────────
    pary_cross = generuj_pary_walutowe(wyniki)
    pary_usd   = generuj_pary_vs_usd(wyniki, flow_globalny)
    # Kontekst sygnału: wydarzenia + reżim + primary_driver + rationale (audit, argumentacja)
    signal_context = {}
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}
    for w in wyniki:
        inst = w["instrument"]
        currency = inst if inst in WALUTY_FX else "USD"
        r = rezimy.get(inst, {}) if regime_ok and rezimy else {}
        signal_context[inst] = {
            "event_risk_level":       w.get("event_risk", "NISKI"),
            "event_high_count":       w.get("event_high_count", 0),
            "upcoming_events_summary": get_upcoming_events_summary(currency, days_ahead=7, max_events=5),
            "regime_type":            r.get("typ_rezimu"),
            "above_ema":              r.get("powyzej_ema"),
        }
    to_save = sorted(pary_usd, key=lambda x: x.get("sila_sygnalu", 0), reverse=True)[:5]
    for p in to_save:
        para = p.get("para", "")
        kierunek = p.get("kierunek", "LONG")
        inst = nazwa_do_inst.get(para, para.split("/")[0] if "/" in para else "")
        w = next((x for x in wyniki if x["instrument"] == inst), None)
        if w and inst in signal_context:
            signal_context[inst]["primary_driver"] = get_primary_driver(w)
            signal_context[inst]["rationale"] = build_rationale(para, kierunek, w, signal_context[inst]["primary_driver"])
    try:
        n_saved = save_signals(report_date, pary_usd, top_n=5, signal_context=signal_context)
        n_updated = update_outcomes(days_ago=21, max_to_check=25)
        if n_saved > 0:
            print(f"  [UCZENIE] Zapisano {n_saved} sygnałów do outcomes.db. Zaktualizowano {n_updated} outcomes (weryfikacja 7/14/21d).")
        else:
            print("  [UCZENIE] Brak sygnałów USD do zapisania – raport bez par vs USD.")
        if n_updated > 0:
            print(f"  [UCZENIE] Dopisano {n_updated} weryfikacji (hit/miss) – używane do learned_conviction i quality.")
    except Exception as e:
        print(f"  [outcome_tracker] Błąd zapisu: {e}")
    drukuj_tabele_par(pary_cross, pary_usd)

    # ── RISK & PORTFOLIO ──────────────────────────────────────
    risk = oblicz_ryzyko_portfela(wyniki, pary_cross, pary_usd, GRUPY_KORELACYJNE)
    print("\n" + S2)
    print("RISK & PORTFOLIO (SofikaMax Agent):")
    print(S2)
    print(f"  {risk['rekomendacja']}")
    print(f"  Aktywne sygnały: {risk['n_aktywne_sygnaly']} | Pary w raporcie: {risk['n_par_w_raporcie']}")
    if risk["exposure"]:
        print("  Ekspozycja grupowa:")
        for grupa, inst in risk["exposure"].items():
            print(f"    {grupa}: {', '.join(inst)}")
    for o in risk["ostrzezenia"]:
        print(f"  [!] {o}")
    print("  [Risk disclosure] " + RISK_DISCLOSURE)
    print()

    # ── WORKFLOW (baza) ─────────────────────────────────────────────────────
    workflow_lines = build_workflow(
        wyniki, pary_usd, top_n=6,
        situation_quality_map=feedback.get("situation_quality_map"),
    )
    # Instrukcja: decyzja, uzasadnienie, sugerowany size, rationale per sygnał
    instr = build_instruction(
        wyniki, pary_usd, risk, feedback, workflow_lines,
        feedback.get("situation_quality_map") or {},
    )
    workflow_lines = instr.get("workflow_lines_enriched", workflow_lines)

    # ── INSTRUKCJA – CO ROBIĆ DZIŚ (czytelna decyzja, argumentacja, ochrona kapitału) ─
    print("\n" + "=" * 78)
    print("  INSTRUKCJA – CO ROBIĆ DZIŚ")
    print("  Agent dba o kapitał: jasna decyzja i uzasadnienie.")
    print("=" * 78)
    decision = instr.get("decision", "WCHODŹ Z OGRANICZENIAMI")
    if decision == "NIE WCHODŹ":
        print("  DECYZJA:  NIE WCHODŹ W NOWE POZYCJE")
    elif decision == "WCHODŹ Z OGRANICZENIAMI":
        print("  DECYZJA:  WCHODŹ Z OGRANICZENIAMI (zmniejsz size, wybierz 1–2 setupy)")
    else:
        print("  DECYZJA:  MOŻESZ WCHODZIĆ (stosuj sugerowany size i max pozycje)")
    print()
    print("  Uzasadnienie:")
    for r in instr.get("reasons", []):
        print(f"    • {r}")
    print()
    if instr.get("top_ideas"):
        print("  Jeśli wchodzisz – top pomysły (sugerowany size + uzasadnienie):")
        for i, idea in enumerate(instr["top_ideas"][:3], 1):
            print(f"    {i}. {idea['co']}  |  Size: {idea['suggested_size_desc']}")
            print(f"       {idea['rationale']}")
        print()
    if instr.get("ryzyka"):
        print("  Ryzyka:")
        for ry in instr["ryzyka"]:
            print(f"    [!] {ry}")
    print("=" * 78)
    print()

    # ── DESK: sugestie zleceń (bez wykonania w raporcie)
    desk_result = {}
    if run_desk_cycle:
        try:
            desk_result = run_desk_cycle(instruction=instr, risk=risk, execute=False, max_orders=3)
            if desk_result.get("suggested_orders"):
                print("\n  DESK – Sugerowane zlecenia (nie wykonane):")
                for o in desk_result["suggested_orders"]:
                    print(f"    • {o.get('side')} {o.get('symbol')} {o.get('size_pct')}% – {o.get('rationale', '')[:60]}")
        except Exception as e:
            print(f"  DESK (pomijam): {e}")

    # ── WORKFLOW – SZCZEGÓŁY (co i jak długo, z size i rationale) ─────────────
    print("\n" + S2)
    print("WORKFLOW – CO I JAK DŁUGO HANDLOWAĆ (szczegóły):")
    print(S2)
    for line in workflow_lines:
        qn = f" | {line.get('quality_note','')}" if line.get("quality_note") else ""
        print(f"  {line['co']:<25} | Horyzont: {line['jak_dlugo']} | {line['conviction']}{qn}")
        print(f"    Sugerowany size: {line.get('suggested_size_desc', '1% kapitału')}")
        print(f"    Uzasadnienie: {line.get('rationale', '')}")
        print(f"    Sytuacja: {line['sytuacja']}  |  Driver: {line.get('primary_driver', '')}")
        print(f"    Wariant A: {line['wariant_a']}")
        print(f"    Wariant B: {line['wariant_b']}")
        try:
            _inst = (line.get("para") or "").split("/")[0] if "/" in (line.get("para") or "") else ""
            _reg = rezimy.get(_inst, {}).get("typ_rezimu") if regime_ok and rezimy else None
            similar = get_similar_signals(line.get("situation_id", "OTHER"), _reg, limit=5)
            if similar:
                hits = sum(1 for s in similar if s.get("hit"))
                print(f"    Analogi (ostatnie {len(similar)}): {hits} trafionych, {len(similar) - hits} nietrafionych")
        except Exception:
            pass
        print()
    print()

    # ── KALIBRACJA CONVICTION (historyczna trafność wg poziomu) ─────────────
    conv_agg = []
    try:
        conv_agg = get_conviction_aggregation(min_samples=1)
        if conv_agg:
            print("\n" + S2)
            print("KALIBRACJA CONVICTION (trafność historyczna wg poziomu, horyzont 14d):")
            print(S2)
            for row in conv_agg:
                print(f"  {row['conviction']:<14} : {row['hit_rate_pct']}% trafionych (n={row['total']})")
            print()
    except Exception:
        pass

    # ── TRAFNOŚĆ WG EVENT RISK (ostrzeżenie przy niskiej trafności w dni z wydarzeniami) ─
    event_agg = []
    try:
        event_agg = get_event_risk_aggregation(min_samples=1)
        if event_agg:
            print("\n" + S2)
            print("TRAFNOŚĆ WG RYZYKA WYDARZEŃ (horyzont 14d):")
            print(S2)
            for row in event_agg:
                print(f"  {row['event_risk_level']:<12} : {row['hit_rate_pct']}% trafionych (n={row['total']})")
            low_event = next((r for r in event_agg if r["event_risk_level"] in ("WYSOKI", "KRYTYCZNY") and r["hit_rate_pct"] < 45), None)
            if low_event:
                print(f"  [!] Ostrzeżenie: przy wysokim ryzyku wydarzeń historyczna trafność była niska – rozważ mniejszą ekspozycję przed NFP/FOMC.")
            print()
    except Exception:
        pass

    # ── WERYFIKACJA SYGNALOW / ANALIZA FEEDBACKU (wyniki z bloku uczenia) ─────
    if feedback.get("co_dziala") or feedback.get("co_nie_dziala") or feedback.get("rekomendacja"):
        print("\n" + S2)
        print("ANALIZA FEEDBACKU (co działa / nie działa):")
        print(S2)
        if feedback.get("co_dziala"):
            print("  Działa (trafność ≥55%):")
            for x in feedback["co_dziala"]:
                print(f"    • {x}")
        if feedback.get("co_nie_dziala"):
            print("  Nie działa (trafność ≤45%):")
            for x in feedback["co_nie_dziala"]:
                print(f"    • {x}")
        if feedback.get("rekomendacja"):
            print("  Rekomendacja workflow:")
            for x in feedback["rekomendacja"]:
                print(f"    {x}")
        print()
    commentary = ""
    if verified:
        print("\n" + S2)
        print("WERYFIKACJA SYGNALOW (ktore sie sprawdzily):")
        print(S2)
        for v in verified[:6]:
            status = "trafiony" if v.get("hit") else "nietrafiony"
            pct = v.get("pct_change")
            pct_str = f"{pct:+.2f}%" if pct is not None else "–"
            print(f"  {v['report_date']} | {v['para']} {v['kierunek']} | {pct_str} -> {status}")
        print()

    # ── KOMENTARZ ANALITYKA ────────────────────────────────────
    try:
        commentary = generuj_komentarz(
            wyniki, makro, flow_globalny, risk, pary_usd, pary_cross, verified=verified
        )
        print("\n" + S2)
        print("KOMENTARZ ANALITYKA:")
        print(S2)
        for line in commentary.split("\n\n"):
            print(f"  {line.strip()}")
        print()
    except Exception as e:
        commentary = ""
        print(f"  [commentary] {e}")

    # ── KARTA DORADCY (jedna spójna rekomendacja + źródła + szac. trafność) ─
    try:
        conv_agg_list = get_conviction_aggregation(min_samples=1)
        trafnosc_szac = ""
        if conv_agg_list:
            w_row = next((r for r in conv_agg_list if r.get("conviction") == "WYSOKI"), None)
            u_row = next((r for r in conv_agg_list if r.get("conviction") == "UMIARKOWANY"), None)
            if w_row:
                trafnosc_szac = f"WYSOKI conviction: ok. {w_row['hit_rate_pct']}% trafionych (n={w_row['total']})"
            elif u_row:
                trafnosc_szac = f"UMIARKOWANY: ok. {u_row['hit_rate_pct']}% trafionych (n={u_row['total']})"
        top_inst = [w["instrument"] for w in wyniki if w.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:3]
        karta_doradcy = {
            "rekomendacja": risk.get("rekomendacja", ""),
            "priorytet_instrumenty": top_inst,
            "max_pozycje_grupa": "max 2 w tej samej grupie korelacyjnej",
            "zrodla": {
                "macro": makro.get("timestamp", "N/A"),
                "cot": "tygodniowe CFTC",
                "flow": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            "trafnosc_szac": trafnosc_szac or "Zbieranie danych weryfikacyjnych.",
        }
        print("\n" + S2)
        print("KARTA DORADCY (rekomendacja + źródła + szac. trafność):")
        print(S2)
        print(f"  Rekomendacja: {karta_doradcy['rekomendacja']}")
        print(f"  Priorytet: {', '.join(karta_doradcy['priorytet_instrumenty']) or 'brak'}")
        print(f"  Źródła: FRED {karta_doradcy['zrodla']['macro']} | COT {karta_doradcy['zrodla']['cot']} | Flow {karta_doradcy['zrodla']['flow']}")
        print(f"  Trafność (historyczna): {karta_doradcy['trafnosc_szac']}")
        print()
    except Exception:
        karta_doradcy = {}

    # Świeżość danych (do payloadu)
    data_freshness = {
        "macro": makro.get("timestamp", "N/A"),
        "cot": "tygodniowe CFTC",
        "flow": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    try:
        user_feedback_agg = get_user_feedback_aggregation()
    except Exception:
        user_feedback_agg = []

    # ── LAYER 2 REGIME ────────────────────────────────────────
    print("\n" + S2)
    print("LAYER 2 - MARKET REGIME (40EMA Weekly + HH/HL + ATR):")
    print(S2)
    if regime_ok and rezimy:
        print("  WALUTA   REZIM                     EMA40   ATR (percentyl/52w)     SCORE")
        print("  " + "-" * 72)
        for inst in INSTRUMENTY:
            if inst in rezimy:
                r   = rezimy[inst]
                et  = "ABOVE" if r.get("powyzej_ema") else ("BELOW" if r.get("powyzej_ema") is False else "N/A")
                ap  = r.get("atr_percentile")
                r52 = r.get("range_52w_pct")
                atr_extra = ""
                if ap is not None:
                    atr_extra = f" p{int(ap)}%"
                if r52 is not None:
                    atr_extra += f" 52w:{int(r52)}%"
                atr_str = (r.get("atr_stan") or "?") + atr_extra
                rt  = " [!RANGE]" if r.get("range_warning") else ""
                print(f"  {inst:<8} {r.get('typ_rezimu','?'):<26} {et:<8} {atr_str:<22} {r.get('score',0)}/20{rt}")
    else:
        print("  Regime engine niedostepny.")

    # ── LAYER 3 FLOW ──────────────────────────────────────────
    print("\n" + S2)
    print("LAYER 3 - INTERMARKET FLOW:")
    if flow_ok and flow_globalny:
        cr = flow_globalny.get("crypto", {})
        print(f"  Rezim:    {flow_globalny.get('rezim','?')} (sila: {flow_globalny.get('rezim_sila',0)}/4)")
        print(f"  Risk-ON:  {flow_globalny.get('risk_on_count',0)}  |  Risk-OFF: {flow_globalny.get('risk_off_count',0)}")
        print(f"  USD:      {flow_globalny.get('usd_kierunek','?')}")
        print(f"  Surowce:  {flow_globalny.get('surowce_kierunek','?')}")
        if cr and cr.get("btc_cena", 0) > 0:
            print(f"  BTC:      {cr.get('btc_trend','?')} | ${cr.get('btc_cena',0):,.0f} | 5d:{cr.get('btc_zmiana_5d',0):+.1f}% | 20d:{cr.get('btc_zmiana_20d',0):+.1f}%")
    else:
        print("  Flow engine niedostepny.")

    # ── KARTY TRANSAKCYJNE ────────────────────────────────────
    print("\n" + S2)
    print("TOP SYGNALY - KARTY TRANSAKCYJNE:")
    top = [w for w in wyniki if w["conviction"] in ["WYSOKI", "UMIARKOWANY"]]
    if top:
        for w in top[:3]:
            drukuj_karte(
                meta={
                    "instrument":   w["instrument"],
                    "meta_bias":    w["meta_bias"],
                    "meta_type":    w["meta_type"],
                    "meta_horizon": w["meta_horizon"],
                    "wariant_a":    w["wariant_a"],
                    "wariant_b":    w["wariant_b"],
                    "conviction":   w["conviction"],
                    "score":        w["lacznie"],
                },
                cot=w["cot_obj"],
                cykl=w["cykl_obj"],
                makro=makro
            )
            s = w["szczegoly"]
            print(f"  Scoring: COT={s['cot']} | Cykl={s['cykl']} | Flow={s['flow']} | Surprise={s['surprise']} | Sentiment={s['sentiment']} | News={s['news']} | Kara={s['kara']} | Lacznie={s['lacznie']}/100")
            cot_obj = w.get("cot_obj") or {}
            if cot_obj.get("cot_interpretation"):
                print(f"  COT vs historia: {cot_obj['cot_interpretation']}")
            if w["top_news"]:
                print(f"  Top news: {w['top_news']}")
            if w["flow_dyw"]:
                print("  [!] DYWERGENCJA FLOW - sygnaly intermarket sprzeczne z biasem!")
    else:
        print("\n  Brak sygnalow WYSOKI/UMIARKOWANY")
        print("  Nie wymuszaj transakcji - czekaj na lepszy setup!")

    # ── KONTEKST MAKRO ────────────────────────────────────────
    print("\n" + S2)
    print("KONTEKST MAKRO (dane z FRED):")
    if makro.get("DXY"):
        trend = "+" if makro["DXY"]["trend"] == "UP" else "-"
        print(f"  Dolar (DXY):         {makro['DXY']['value']} ({trend})")
    if makro.get("US10Y"):
        trend = "+" if makro["US10Y"]["trend"] == "UP" else "-"
        print(f"  Obligacje US 10Y:    {makro['US10Y']['value']}% ({trend})")
    if makro.get("YIELD_CURVE") is not None:
        yc = makro["YIELD_CURVE"]
        print(f"  Krzywa dochodowosci: {yc:+.2f} ({'NORMALNA' if yc > 0 else 'ODWROCONA!'})")
    if makro.get("FEDFUNDS"):
        print(f"  Stopa FED:           {makro['FEDFUNDS']['value']}%")
    if makro.get("CPI"):
        trend = "+" if makro["CPI"]["trend"] == "UP" else "-"
        print(f"  Inflacja CPI:        {makro['CPI']['value']} ({trend})")
    if makro.get("UNRATE"):
        trend = "+" if makro["UNRATE"]["trend"] == "UP" else "-"
        print(f"  Bezrobocie USA:      {makro['UNRATE']['value']}% ({trend})")
    if makro.get("OIL_WTI"):
        trend = "+" if makro["OIL_WTI"]["trend"] == "UP" else "-"
        print(f"  Ropa WTI:            ${makro['OIL_WTI']['value']} ({trend})")
    if makro.get("REAL_YIELD_10Y") is not None:
        ry = makro["REAL_YIELD_10Y"]
        print(f"  Real yield 10Y:       {ry:+.2f}% (ujemny = wsparcie dla zlota)")

    # ── GLOBAL YIELDS (Money.net) – opcjonalnie gdy klucz API ustawiony ─
    global_yields = None
    if money_net_get_global_yields is not None:
        try:
            global_yields = money_net_get_global_yields()
        except Exception:
            pass
    if global_yields and isinstance(global_yields, dict):
        ts = global_yields.get("timestamp", "")
        yield_items = [(k, v) for k, v in global_yields.items() if k != "timestamp" and isinstance(v, (int, float))]
        if yield_items:
            print("\n" + S2)
            print("GLOBAL YIELDS (Money.net):")
            print(S2)
            for k, v in sorted(yield_items):
                print(f"  {k} 10Y:   {v:.2f}%")
            if ts:
                print(f"  (zrodlo: Money.net, {ts})")
            print()

    # ── STOPKA ────────────────────────────────────────────────
    print("\n" + S2)
    print(f"SofikaMax Agent | Raport: {tryb} | {datetime.now().strftime('%d.%m.%Y o godz. %H:%M')}")
    print("Dane: CFTC + FRED + ForexFactory + NewsAPI + yfinance(ETF+Weekly)" + (" + Money.net" if global_yields else ""))
    print("Warstwy: COT(20) + Regime/Cykl(20) + Flow(20) + Surprise(20) + Sentiment(20) + News(20) - Kary")
    print("Nastepne raporty: 07:00 | 12:30 | 18:30 | 20:30")
    print("COT is contextual, not predictive.")
    print(S2)

    # Zapis do RAG (kontekst dla LLM w kolejnych raportach)
    if rag_add_report is not None:
        try:
            report_date = datetime.now().strftime("%Y-%m-%d")
            wf_lines = "\n".join([f"  {l['co']} {l['conviction']} | {l['sytuacja']}" for l in workflow_lines[:5]])
            report_summary = f"Raport {report_date}. Workflow:\n{wf_lines}\nRisk: {risk.get('rekomendacja', '')}"
            rag_add_report(report_date, report_summary, {"workflow_count": len(workflow_lines)})
            if feedback.get("co_dziala") or feedback.get("co_nie_dziala") or feedback.get("rekomendacja"):
                fb_lines = (feedback.get("co_dziala") or []) + (feedback.get("co_nie_dziala") or []) + (feedback.get("rekomendacja") or [])
                rag_add_feedback(" | ".join(fb_lines[:8]))
            if verified:
                hit = sum(1 for v in verified if v.get("hit"))
                rag_add_outcomes(f"Weryfikacja: {hit}/{len(verified)} trafionych. Ostatnie: " + "; ".join([f"{v.get('para','')} {v.get('kierunek','')} {'OK' if v.get('hit') else 'X'}" for v in verified[:5]]))
            if claude_insight and rag_add_claude_insight is not None:
                rag_add_claude_insight(claude_insight, {"report_date": report_date})
        except Exception:
            pass

    # ── Claude: analiza danych historycznych z archiwum ─────────────────────
    claude_insight = None
    try:
        from config import CLAUDE_ENABLED
        if CLAUDE_ENABLED:
            from claude_analyzer import get_analysis_for_report
            claude_insight = get_analysis_for_report()
            if claude_insight:
                print("\n" + S2)
                print("CLAUDE – analiza danych historycznych (z archiwum)")
                print(S2)
                print(claude_insight)
                print(S2)
    except Exception as e:
        print("  Claude (pomijam):", e)

    # Strategic Intelligence – jeden spójny blok: makro, ryzyko, narracja, cykl, rotacja, governor
    strategic = _build_strategic_posture(makro, flow_globalny, risk, instr, commentary)
    if strategic and strategic.get("global"):
        print("\n" + S2)
        print("--- STRATEGIC POSTURE ---")
        print(S2)
        g = strategic["global"]
        print(f"  Macro Mode: {g.get('macro_mode', '?')}")
        print(f"  Risk Score: {g.get('risk_score', '?')}")
        print(f"  Dominant Narrative: {g.get('dominant_narrative', '?')}")
        print(f"  Cycle: {g.get('cycle_mode', '?')}")
        print(f"  Rotation: {g.get('rotation_spec', '?')}")
        print(f"  Deployment Governor: {g.get('deployment_governor', '?')}")
        print()

    payload = {
        "pary_cross":              pary_cross,
        "pary_usd":                pary_usd,
        "flow_globalny":           flow_globalny,
        "rezimy":                  rezimy,
        "regime_ok":               regime_ok,
        "flow_ok":                 flow_ok,
        "risk":                    risk,
        "workflow":                workflow_lines,
        "feedback":                feedback,
        "commentary":              commentary,
        "verified":                 verified,
        "tryb":                    tryb,
        "timestamp":               datetime.now().strftime("%d.%m.%Y %H:%M"),
        "data_freshness":          data_freshness,
        "karta_doradcy":           karta_doradcy,
        "conviction_calibration":  conv_agg,
        "event_risk_aggregation":  event_agg,
        "user_feedback":           user_feedback_agg,
        "global_yields":           global_yields if global_yields else None,
        "instrukcja":              {
            "decision":   instr.get("decision"),
            "reasons":    instr.get("reasons", []),
            "top_ideas":  instr.get("top_ideas", []),
            "ryzyka":     instr.get("ryzyka", []),
        },
        "risk_disclosure":         RISK_DISCLOSURE,
        "desk":                    desk_result,
        "cot_insights":            [
            {
                "instrument": w["instrument"],
                "cot_interpretation": (w.get("cot_obj") or {}).get("cot_interpretation"),
                "percentile_1y": (w.get("cot_obj") or {}).get("percentile_1y"),
                "extreme_type": (w.get("cot_obj") or {}).get("extreme_type"),
                "trend_4w": (w.get("cot_obj") or {}).get("trend_4w_direction"),
            }
            for w in wyniki if (w.get("cot_obj") or {}).get("cot_interpretation")
        ],
        "history_sources":         _get_history_sources(),
        "claude_insight":          claude_insight,
        "strategic":               strategic,
    }
    return wyniki, makro, payload


def _build_strategic_posture(makro, flow_globalny, risk, instr, commentary) -> dict:
    """
    Buduje blok Strategic Posture z istniejących danych (makro, flow, risk, instrukcja, komentarz).
    Używane w raporcie, PDF i dashboardzie jako jedna spójna „karta” postawy strategicznej.
    """
    try:
        cykl_usd = get_cycle_phase("USD")
        cycle_mode = f"{cykl_usd.get('phase', '?')} / {cykl_usd.get('clock', '?')}"
    except Exception:
        cycle_mode = "?"

    # Macro mode: z makro (DXY + score) lub z cyklu USD
    macro_mode = "?"
    if makro:
        dxy = (makro.get("DXY") or {}).get("trend", "")
        if dxy == "DOWN":
            macro_mode = "RISK_ON (DXY słabszy)"
        elif dxy == "UP":
            macro_mode = "RISK_OFF (DXY silniejszy)"
        if macro_mode == "?" and makro.get("macro_score") is not None:
            macro_mode = f"Score {makro.get('macro_score')}/20"

    # Risk: rekomendacja jako „score” opisowy
    risk_score = (risk or {}).get("rekomendacja", "?")
    if risk_score and len(risk_score) > 60:
        risk_score = risk_score[:57] + "..."

    # Dominant narrative: pierwsza linia komentarza
    dominant_narrative = "?"
    if commentary and isinstance(commentary, str) and commentary.strip():
        first_line = commentary.strip().split("\n")[0].strip()
        dominant_narrative = first_line[:120] + ("..." if len(first_line) > 120 else "")

    # Rotation: flow (rezim + kierunek USD)
    rotation_spec = "?"
    if flow_globalny:
        r = flow_globalny.get("rezim", "?")
        u = flow_globalny.get("usd_kierunek", "?")
        rotation_spec = f"{r} | USD {u}"

    # Deployment governor: decyzja z instrukcji
    deployment_governor = (instr or {}).get("decision", "?")

    return {
        "global": {
            "macro_mode": macro_mode,
            "risk_score": risk_score,
            "dominant_narrative": dominant_narrative,
            "cycle_mode": cycle_mode,
            "rotation_spec": rotation_spec,
            "deployment_governor": deployment_governor,
        }
    }


def _get_history_sources():
    """Dostepne zrodla w archiwum (dla AI, np. Cuade)."""
    try:
        from history_archive import get_available_sources
        return get_available_sources()
    except Exception:
        return {}


if __name__ == "__main__":
    generuj_raport(tryb="TESTOWY")