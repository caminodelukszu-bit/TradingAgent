# =============================================================================
# claude_sentiment.py - Sentyment z Claude na podstawie nagłówków newsów
# Fallback gdy MyFXBook nie zwraca danych (Invalid session) lub jako uzupełnienie.
# =============================================================================

import re
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    from config import CLAUDE_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS
except ImportError:
    CLAUDE_API_KEY = ""
    CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
    CLAUDE_MAX_TOKENS = 500

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _headlines_for_instrument(instrument: str, max_articles: int = 8) -> List[str]:
    """Pobiera nagłówki (title + description) dla instrumentu z NewsAPI."""
    try:
        from news_engine import pobierz_newsy
        articles = pobierz_newsy(instrument.upper(), limit=max_articles)
    except ImportError:
        return []
    lines = []
    for a in (articles or [])[:max_articles]:
        title = (a.get("title") or "").strip()
        desc = (a.get("description") or "").strip()
        if title:
            lines.append(title)
        if desc and desc != title:
            lines.append(desc[:200])
    return lines


def get_claude_sentiment(instrument: str, headlines: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Ocena sentymentu rynkowego dla instrumentu na podstawie nagłówków – przez Claude.
    Zwraca słownik w kształcie zgodnym z sentiment_engine: score (0-20), bias (BUY/SELL/NEUTRALNY),
    poziom_retail_long (None – nie mierzymy retailu), source="claude", rationale.
    """
    empty = {
        "instrument":          instrument.upper(),
        "score":               0,
        "bias":                "NEUTRALNY",
        "poziom_retail_long":  None,
        "capitulation_alert":   False,
        "long_positions":      None,
        "short_positions":     None,
        "total_positions":     None,
        "source":              "claude",
        "rationale":           "",
        "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if not CLAUDE_API_KEY or not CLAUDE_API_KEY.strip():
        return empty
    if headlines is None:
        headlines = _headlines_for_instrument(instrument)
    if not headlines:
        empty["rationale"] = "Brak nagłówków do analizy."
        return empty

    text = "\n".join([f"- {h}" for h in headlines[:15]])
    system = """Jesteś analitykiem sentymentu rynkowego. Dostajesz listę nagłówków newsów.
Na podstawie TYLKO tych nagłówków oceń sentyment rynkowy (nastawienie inwestorów/mediów) dla podanego instrumentu.
Odpowiedz wyłącznie w trzech liniach w formacie (bez dodatkowego tekstu):
KIERUNEK=POZYTYWNY lub KIERUNEK=NEGATYWNY lub KIERUNEK=NEUTRALNY
SILA=liczba od 1 do 10 (1=brak kierunku, 10=bardzo silny sentyment)
UZASADNIENIE=jedno krótkie zdanie po polsku"""
    user = f"Instrument: {instrument.upper()}\n\nNagłówki:\n{text}"
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
            timeout=30,
        )
        if r.status_code != 200:
            empty["rationale"] = f"API {r.status_code}"
            return empty
        data = r.json()
        content = data.get("content", [])
        response_text = ""
        for block in content:
            if block.get("type") == "text":
                response_text += block.get("text", "")
        response_text = response_text.strip()

        # Parsowanie KIERUNEK, SILA, UZASADNIENIE
        kierunek = "NEUTRALNY"
        sila = 5
        uzasadnienie = ""
        for line in response_text.upper().split("\n"):
            line = line.strip()
            if line.startswith("KIERUNEK="):
                val = line.split("=", 1)[1].strip()
                if "POZYTYWNY" in val or "BULLISH" in val:
                    kierunek = "POZYTYWNY"
                elif "NEGATYWNY" in val or "BEARISH" in val:
                    kierunek = "NEGATYWNY"
                else:
                    kierunek = "NEUTRALNY"
            elif line.startswith("SILA=") or line.startswith("SIŁA="):
                m = re.search(r"(\d+)", line.replace("SILA=", "").replace("SIŁA=", ""))
                if m:
                    sila = max(1, min(10, int(m.group(1))))
            elif line.startswith("UZASADNIENIE="):
                uzasadnienie = line.split("=", 1)[1].strip() if "=" in line else ""
        if not uzasadnienie:
            uzasadnienie = response_text[:200]

        # Mapowanie na format sentiment_engine: bias BUY/SELL/NEUTRALNY, score 0-20
        if kierunek == "POZYTYWNY":
            bias = "BUY"
        elif kierunek == "NEGATYWNY":
            bias = "SELL"
        else:
            bias = "NEUTRALNY"
        score = round((sila / 10) * 20)
        score = max(0, min(20, score))

        return {
            "instrument":          instrument.upper(),
            "score":               score,
            "bias":                bias,
            "poziom_retail_long":  None,
            "capitulation_alert":   False,
            "long_positions":      None,
            "short_positions":     None,
            "total_positions":     None,
            "source":              "claude",
            "rationale":           uzasadnienie[:300],
            "timestamp":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        empty["rationale"] = str(e)[:200]
        return empty
