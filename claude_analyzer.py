# =============================================================================
# claude_analyzer.py - Analiza danych historycznych przez Claude (Anthropic API)
# Czyta z history_archive, wysyła kontekst do Claude, zwraca wnioski do raportu.
# =============================================================================

import requests
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from config import CLAUDE_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS
except ImportError:
    CLAUDE_API_KEY = ""
    CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
    CLAUDE_MAX_TOKENS = 1500

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


# Wszystkie serie FRED z makro (DXY, stopy, CPI, bezrobocie, ropa)
FRED_SERIES_FOR_CONTEXT = [
    ("DTWEXBGS", "DXY"),
    ("DGS10", "US10Y"),
    ("DGS2", "US2Y"),
    ("FEDFUNDS", "FEDFUNDS"),
    ("CPIAUCSL", "CPI"),
    ("UNRATE", "UNRATE"),
    ("GDP", "GDP"),
    ("DCOILWTICO", "OIL_WTI"),
]
# Flow ETF (risk-on/off, USD, waluty, surowce)
FLOW_TICKERS = ["SPY", "GLD", "TLT", "UUP", "FXE", "USO"]
# Regime weekly (główne pary + złoto)
REGIME_TICKERS = ["EUR", "GBP", "JPY", "AUD", "GOLD"]
# COT z cot_archive (pozycja netto)
COT_INSTRUMENTS = ["EUR", "GBP", "JPY", "GOLD", "SILVER"]
# News sentyment
NEWS_INSTRUMENTS = ["USD", "EUR", "GOLD"]


def _build_history_context(max_fred_points: int = 80, max_flow_days: int = 120, max_regime_weeks: int = 52, max_cot_weeks: int = 52) -> str:
    """Buduje rozbudowany kontekst z archiwum: FRED, flow, regime, COT, news, events."""
    try:
        from history_archive import (
            get_available_sources,
            get_history_fred,
            get_history_flow,
            get_history_regime,
            get_history_news,
            get_history_events,
        )
    except ImportError:
        return "Brak modułu history_archive."
    sources = get_available_sources()
    lines = ["# Dostępne źródła w archiwum", str(sources), ""]
    # FRED – wszystkie kluczowe serie
    for sid, name in FRED_SERIES_FOR_CONTEXT:
        df = get_history_fred(sid, limit=max_fred_points)
        if df is not None and len(df) > 0:
            last = df.tail(8)
            lines.append(f"## FRED {name} ({sid}) – ostatnie 8 odczytów")
            lines.append(last.to_string(index=False))
            lines.append("")
    # Flow ETF
    for ticker in FLOW_TICKERS:
        df = get_history_flow(ticker, days=max_flow_days)
        if df is not None and len(df) >= 5:
            last = df.tail(5)
            cols = ["date", "Close"] if "Close" in last.columns else [last.columns[0], last.columns[3] if len(last.columns) > 3 else last.columns[-1]]
            last = last[cols] if all(c in last.columns for c in cols) else last.tail(5)
            lines.append(f"## Flow ETF {ticker} – ostatnie 5 sesji")
            lines.append(last.to_string(index=False))
            lines.append("")
    # Regime weekly
    for ticker in REGIME_TICKERS:
        df = get_history_regime(ticker, weeks=max_regime_weeks)
        if df is not None and len(df) >= 3:
            last = df.tail(5)
            cols = ["date", "Close"] if "Close" in last.columns else list(last.columns[:2])
            last = last[cols]
            lines.append(f"## Regime weekly {ticker} – ostatnie 5 tygodni (Close)")
            lines.append(last.to_string(index=False))
            lines.append("")
    # COT (z cot_archive)
    try:
        from cot_archive import get_cot_history
        for inst in COT_INSTRUMENTS:
            df = get_cot_history(inst, weeks=max_cot_weeks)
            if df is not None and len(df) >= 5:
                last = df.tail(8)[["date", "net_position", "net_change"]]
                lines.append(f"## COT {inst} – pozycja netto (ostatnie 8 tygodni)")
                lines.append(last.to_string(index=False))
                lines.append("")
    except ImportError:
        pass
    # News sentyment (ostatnie dni)
    for inst in NEWS_INSTRUMENTS:
        df = get_history_news(inst, days=14)
        if df is not None and len(df) > 0:
            last = df.tail(5)
            lines.append(f"## News sentyment {inst} – ostatnie 5 dni")
            lines.append(last.to_string(index=False))
            lines.append("")
    # Wydarzenia
    events = get_history_events(limit=20)
    if events:
        lines.append("## Wydarzenia w kalendarzu (z archiwum)")
        for e in events[:12]:
            lines.append(f"  {e.get('event_date')} {e.get('currency')} {e.get('event_name')} [{e.get('impact')}]")
        lines.append("")
    return "\n".join(lines)


def analyze_history() -> Dict[str, Any]:
    """
    Wysyła kontekst z archiwum do Claude i zwraca wnioski.
    Zwraca: {"ok": bool, "summary": str, "error": str|None}
    """
    if not CLAUDE_API_KEY or not CLAUDE_API_KEY.strip():
        return {"ok": False, "summary": "", "error": "Brak CLAUDE_API_KEY w config."}
    context = _build_history_context()
    if not context or "Brak modułu" in context:
        return {"ok": False, "summary": "", "error": "Brak danych z archiwum lub brak modułu."}
    system = """Jesteś analitykiem rynkowym. Dostajesz zrzut danych historycznych z archiwum (FRED, flow ETF, regime weekly, wydarzenia).
Twoje zadanie: na podstawie TYLKO tych danych (bez domysłów) napisz zwięzły raport 4–8 zdań po polsku:
1) Gdzie jesteśmy vs historia – czy któreś serie są blisko ekstremów (np. DXY, stopy, COT).
2) Co z dynamiki ostatnich tygodni – kierunek (risk-on/off, USD, surowce).
3) Krótko: główne ryzyka i szanse na najbliższe 1–2 tygodnie.
Bądź konkretny, unikaj ogólników. Jeśli danych mało – napisz co widać i że potrzeba więcej historii."""
    user = f"Dane z archiwum (stan na {datetime.now().strftime('%Y-%m-%d %H:%M')}):\n\n{context}"
    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": CLAUDE_MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=60,
        )
        if r.status_code != 200:
            return {"ok": False, "summary": "", "error": f"API {r.status_code}: {r.text[:300]}"}
        data = r.json()
        content = data.get("content", [])
        text = ""
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")
        return {"ok": True, "summary": text.strip(), "error": None}
    except Exception as e:
        return {"ok": False, "summary": "", "error": str(e)}


def get_analysis_for_report() -> Optional[str]:
    """Wywołuje analyze_history() i zwraca summary do wstawienia w raport (lub None)."""
    out = analyze_history()
    if out.get("ok") and out.get("summary"):
        return out["summary"]
    return None


def ask_claude(user_question: str) -> Dict[str, Any]:
    """
    Wysyła własne pytanie użytkownika + kontekst z archiwum do Claude.
    Zwraca: {"ok": bool, "summary": str, "error": str|None}
    """
    if not CLAUDE_API_KEY or not CLAUDE_API_KEY.strip():
        return {"ok": False, "summary": "", "error": "Brak CLAUDE_API_KEY w config."}
    context = _build_history_context()
    if not context or "Brak modułu" in context:
        return {"ok": False, "summary": "", "error": "Brak danych z archiwum."}
    system = """Jesteś analitykiem rynkowym. Dostajesz pytanie użytkownika oraz zrzut danych historycznych (FRED, flow ETF, regime, COT, news, wydarzenia).
Odpowiadaj konkretnie na podstawie TYLKO tych danych. Po polsku. Jeśli danych brak – napisz wprost."""
    user = f"Kontekst (dane z archiwum, stan na {datetime.now().strftime('%Y-%m-%d %H:%M')}):\n\n{context}\n\n---\n\nPytanie użytkownika: {user_question}"
    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": CLAUDE_MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=90,
        )
        if r.status_code != 200:
            return {"ok": False, "summary": "", "error": f"API {r.status_code}: {r.text[:400]}"}
        data = r.json()
        content = data.get("content", [])
        text = ""
        for block in content:
            if block.get("type") == "text":
                text += block.get("text", "")
        return {"ok": True, "summary": text.strip(), "error": None}
    except Exception as e:
        return {"ok": False, "summary": "", "error": str(e)}
