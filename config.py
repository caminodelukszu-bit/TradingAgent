# ============================================================
# SofikaMax Agent - CONFIG
# ============================================================
#
# KLUCZE API – DO CZEGO SŁUŻĄ (wartości w .env, opis w .env.example):
#   FRED_API_KEY       → dane makro (macro_engine, surprise_engine), fred.stlouisfed.org
#   MYFXBOOK_EMAIL/PWD → sentyment retail (sentiment_engine), myfxbook.com
#   LLM_API_KEY        → komentarz analityka (commentary_engine), OpenAI/Azure/Ollama
#   MONEY_NET_API_KEY  → sekcja Global Yields w raporcie (money_net_engine)
#   GUARDIAN_API_KEY   → news Guardian (opcjonalnie)
#   NYT_API_KEY        → news NYT (opcjonalnie)
#   CLAUDE_API_KEY     → analiza archiwum + fallback sentymentu (claude_analyzer, claude_sentiment)
#   ADMIN_PASSWORD     → panel Subskrypcje w dashboardzie
#
# ============================================================

from pathlib import Path
import os

# Ładowanie .env z katalogu projektu (obok config.py)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

# -----------------------------------------------------------------------------
# Klucze API i hasła (z .env lub zmiennych środowiskowych)
# -----------------------------------------------------------------------------
# FRED – dane makro (St. Louis Fed). Używane przez: macro_engine, surprise_engine.
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# MyFXBook – sentyment retail (Layer 4b). Limit 100 zapytan/24h. Puste = neutral.
# Używane przez: sentiment_engine.
MYFXBOOK_EMAIL    = os.environ.get("MYFXBOOK_EMAIL", "")
MYFXBOOK_PASSWORD = os.environ.get("MYFXBOOK_PASSWORD", "")

# Waluty
CURRENCIES = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

# Futures
FUTURES = ["GOLD", "SILVER", "COPPER", "OIL"]

# Crypto
CRYPTO = ["BTC"]

# Progi conviction
CONVICTION_HIGH     = 80
CONVICTION_MODERATE = 60
CONVICTION_LOW      = 40

# Kary (penalty)
PENALTY_EVENT_RISK  = -15
PENALTY_DIVERGENCE  = -10
PENALTY_OI_FALLING  = -10
PENALTY_RANGE       = -10

# Limity instytucjonalne (exposure control – banki/fundusze)
MAX_POSITIONS_TOTAL       = 5   # max równoczesnych pozycji
MAX_POSITIONS_IN_GROUP     = 2   # max pozycji w jednej grupie korelacyjnej
MAX_EXPOSURE_PCT_CURRENCY  = 10  # max % kapitału łącznie na jedną walutę (rekomendacja)

# Desk (execution + pozycje): paper = symulacja w desk.db, live = tylko sugestie (bez auto)
DESK_MODE       = "paper"   # paper | live
BROKER_ADAPTER  = "paper"   # paper | mt5 | oanda (w przyszłości)
PAPER_CAPITAL   = 0.0       # kapitał symulowany (0 = brak); w live z brokera

# Horyzont
HORIZON = "1-4w"

# Archiwum raportów – analiza kwartalna przed wydaniem bieżącego raportu
# Ostatnie N raportów podlega analizie (4/dzień → ~31 dni ≈ 124; 123 = pełny kwartał pod kontrolą)
QUARTER_REPORTS_LIMIT = 123

# Subskrypcje (kto dostaje raporty na Telegram)
# Sciezka do bazy SQLite. Wspoldziel ten plik miedzy komputerami lub trzymaj na serwerze.
SUBSCRIPTION_DB_PATH = "subscriptions.db"

# Haslo do panelu Admin (Dashboard -> zakladka Subskrypcje). Z .env: ADMIN_PASSWORD.
# Zostaw puste = zakladka Subskrypcje niewidoczna (raporty ida do AUTORYZOWANI z telegram_bot).
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Dostep do Dashboard: True = obcy musza podac token LUB haslo admina. False = bez logowania (tylko lokalnie).
DASHBOARD_REQUIRE_TOKEN = False

# -----------------------------------------------------------------------------
# LLM (komentarz analityka, podsumowania) – SofikaMax Agent
# -----------------------------------------------------------------------------
# LLM – komentarz analityka. Z .env: LLM_API_KEY. Pusty = komentarz tylko z szablonu.
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# Opcjonalnie: base URL (np. Azure lub http://localhost:11434/v1 dla Ollama). Z .env: LLM_BASE_URL.
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")

# Model: gpt-4o-mini (tani, szybki), gpt-4o (lepsza jakosc), lub nazwa modelu lokalnego (Ollama).
LLM_MODEL = "gpt-4o-mini"

# Limity
LLM_MAX_TOKENS = 800
LLM_TIMEOUT_SEC = 30

# RAG: ile ostatnich wpisow (raporty + feedback + outcomes) dolaczac do kontekstu dla LLM.
RAG_CONTEXT_ITEMS = 12

# -----------------------------------------------------------------------------
# Money.net API (globalne stopy, FX, news – opcjonalnie)
# -----------------------------------------------------------------------------
# Money.net – sekcja Global Yields. Z .env: MONEY_NET_API_KEY. Pusty = sekcja pomijana.
MONEY_NET_API_KEY = os.environ.get("MONEY_NET_API_KEY", "")

# Opcjonalnie: base URL API. Z .env: MONEY_NET_BASE_URL.
MONEY_NET_BASE_URL = os.environ.get("MONEY_NET_BASE_URL", "")

# Timeout zapytan (sekundy)
MONEY_NET_TIMEOUT_SEC = 15

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Źródła wiadomości (news) – preferowane agencje/redakcje (Reuters, AP, BBC, itd.)
# Używane do sortowania/priorytetu przy NewsAPI; osobne API (Guardian, NYT) – opcjonalnie w przyszłości.
# -----------------------------------------------------------------------------
NEWS_PREFERRED_SOURCES = [
    "Reuters", "Associated Press", "AFP", "Agence France-Presse",
    "BBC News", "The Guardian", "The New York Times", "Wall Street Journal",
    "The Economist", "PBS NewsHour", "Deutsche Welle", "Al Jazeera English",
]
# News – opcjonalne (puste = tylko NewsAPI). Z .env: GUARDIAN_API_KEY, NYT_API_KEY.
GUARDIAN_API_KEY = os.environ.get("GUARDIAN_API_KEY", "")
NYT_API_KEY = os.environ.get("NYT_API_KEY", "")

# Dodatkowe kanały RSS źródeł oficjalnych (np. Biały Dom, Ministerstwo Finansów). Lista dict: {"url": "...", "name": "...", "region": "USA"}
OFFICIAL_FEEDS_EXTRA = []

# -----------------------------------------------------------------------------
# Claude / Cuade AI (analiza danych historycznych z archiwum)
# -----------------------------------------------------------------------------
# Claude (Anthropic) – analiza archiwum + fallback sentymentu. Z .env: CLAUDE_API_KEY. Format: sk-ant-api03-...
# Pusty = analiza przez Claude wyłączona.
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
# Wlacz/wylacz analize (True = Claude czyta archiwum i dodaje wnioski do raportu).
CLAUDE_ENABLED = True
# Model: claude-3-5-sonnet-20241022 (domyslny), claude-3-haiku (szybszy, tanszy).
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS = 1500
# Gdy True: przy braku danych MyFXBook używaj sentymentu z Claude (na podstawie nagłówków newsów).
CLAUDE_SENTIMENT_FALLBACK = True