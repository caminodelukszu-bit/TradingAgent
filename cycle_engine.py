from macro_engine import get_fred
import pandas as pd
from datetime import datetime

def get_cycle_phase(currency: str) -> dict:
    """
    Okreslа фазę cyklu ekonomicznego dla danej waluty.
    Bazuje na CLI (Composite Leading Indicator) z danych makro.
    """

    # Mapowanie walut na serie FRED
    CURRENCY_MAP = {
        "USD": {"cli": "USALOLITONOSTSAM", "cpi": "CPIAUCSL",   "unemp": "UNRATE"},
        "EUR": {"cli": "FRАЛOLITONOSTSAM", "cpi": "CP0000EZ19M086NEST", "unemp": "LRHUTTTTEZM156S"},
        "GBP": {"cli": "GBRLOLITONOSTSAM", "cpi": "GBRCPIALLMINMEI",    "unemp": "LRHUTTTTGBM156S"},
        "JPY": {"cli": "JPNLOLITONOSTSAM", "cpi": "JPNCPIALLMINMEI",    "unemp": "LRHUTTTTJPM156S"},
        "AUD": {"cli": "AUSLOLITONOSTSAM", "cpi": "AUSCPIALLQINMEI",    "unemp": "LRHUTTTTAUM156S"},
        "CAD": {"cli": "CANLOLITONOSTSAM", "cpi": "CPALCY01CAM661N",    "unemp": "LRHUTTTTCAM156S"},
        "CHF": {"cli": "CHELOLITONOSTSAM", "cpi": "CHECPIALLMINMEI",    "unemp": "LRHUTTTTCHM156S"},
        "NZD": {"cli": "NZLLOLITONOSTSAM", "cpi": "NZLCPIALLQINMEI",    "unemp": "LRHUTTTTCZM156S"},
    }

    cfg = CURRENCY_MAP.get(currency.upper())
    if not cfg:
        return _empty_result(currency)

    # Pobierz CLI (Composite Leading Indicator)
    cli_df = get_fred(cfg["cli"], limit=12)
    cpi_df = get_fred(cfg["cpi"], limit=6)
    une_df = get_fred(cfg["unemp"], limit=6)

    if cli_df is None or len(cli_df) < 4:
        return _empty_result(currency)

    # CLI value, slope (dlugi: -4 okresy), momentum (krotki: ostatnie 3 odczyty)
    cli_now = cli_df["value"].iloc[-1]
    cli_prev = cli_df["value"].iloc[-4]  # ok. 3 miesiace temu
    cli_slope = cli_now - cli_prev
    if len(cli_df) >= 3:
        recent_slope = (cli_df["value"].iloc[-1] - cli_df["value"].iloc[-3]) / 2.0
        cli_momentum = "POPRAWIA SIE" if recent_slope > 0.05 else ("POGARSZA SIE" if recent_slope < -0.05 else "STABILNY")
    else:
        cli_momentum = "STABILNY"

    # CPI trend
    cpi_rising = False
    if cpi_df is not None and len(cpi_df) >= 2:
        cpi_rising = cpi_df["value"].iloc[-1] > cpi_df["value"].iloc[-2]

    # Unemployment trend
    une_falling = False
    if une_df is not None and len(une_df) >= 2:
        une_falling = une_df["value"].iloc[-1] < une_df["value"].iloc[-2]

    # Faza cyklu (jak BofA Investment Clock)
    if cli_now > 100 and cli_slope > 0:
        phase = "EXPANSION"
    elif cli_now > 100 and cli_slope <= 0:
        phase = "SLOWDOWN"
    elif cli_now <= 100 and cli_slope <= 0:
        phase = "CONTRACTION"
    else:
        phase = "RECOVERY"

    # Zegar ekonomiczny (Goldilocks/Reflation/Stagflation/Deflation)
    if phase in ["EXPANSION", "RECOVERY"] and not cpi_rising:
        clock = "GOLDILOCKS"
    elif phase in ["EXPANSION", "SLOWDOWN"] and cpi_rising:
        clock = "REFLATION"
    elif phase in ["SLOWDOWN", "CONTRACTION"] and cpi_rising:
        clock = "STAGFLATION"
    else:
        clock = "DEFLATION"

    # Dojrzałość fazy (EARLY/MID/LATE)
    if abs(cli_slope) > 0.3:
        maturity = "EARLY"
    elif abs(cli_slope) > 0.1:
        maturity = "MID"
    else:
        maturity = "LATE"

    # Score (0-20) dla Layer 2
    score = 0
    if phase == "EXPANSION":
        score += 10
    elif phase == "RECOVERY":
        score += 8
    elif phase == "SLOWDOWN":
        score += 4
    else:
        score += 0

    if clock == "GOLDILOCKS":
        score += 10
    elif clock == "REFLATION":
        score += 6
    elif clock == "DEFLATION":
        score += 4
    else:
        score += 2

    return {
        "currency":      currency,
        "phase":         phase,
        "clock":         clock,
        "maturity":      maturity,
        "cli":           round(cli_now, 1),
        "cli_slope":     round(cli_slope, 2),
        "cli_momentum":  cli_momentum,
        "score":         min(20, score),
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M")
    }


def _empty_result(currency: str) -> dict:
    return {
        "currency":      currency,
        "phase":         "UNKNOWN",
        "clock":         "UNKNOWN",
        "maturity":      "UNKNOWN",
        "cli":           0,
        "cli_slope":     0,
        "cli_momentum":  "STABILNY",
        "score":         0,
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M")
    }


if __name__ == "__main__":
    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"]

    print(f"\n{'='*65}")
    print(f"{'CYCLE INTELLIGENCE':^65}")
    print(f"{'='*65}")
    print(f"{'WALUTA':<8} {'PHASE':<14} {'CLOCK':<14} {'CLI':<8} {'SLOPE':<8} {'MATURITY'}")
    print(f"{'-'*65}")

    for cur in currencies:
        r = get_cycle_phase(cur)
        print(
            f"{r['currency']:<8} "
            f"{r['phase']:<14} "
            f"{r['clock']:<14} "
            f"{r['cli']:<8} "
            f"{r['cli_slope']:<8} "
            f"{r['maturity']}"
        )
    print(f"{'='*65}")