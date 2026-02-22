# =============================================================================
# money_net_engine.py - SofikaMax Agent
# Opcjonalna warstwa: globalne stopy (yields), ewentualnie FX/news z Money.net API.
# Gdy brak klucza lub blad API – zwracamy None / pusty dict (graceful fallback).
#
# Po zalogowaniu do Money.net: ustaw MONEY_NET_API_KEY w config.py
# i dopasuj endpointy/symbole ponizej do dokumentacji ich API.
# =============================================================================

from typing import Dict, Any, Optional

def _config() -> dict:
    try:
        from config import MONEY_NET_API_KEY, MONEY_NET_BASE_URL, MONEY_NET_TIMEOUT_SEC
        return {
            "api_key": MONEY_NET_API_KEY or "",
            "base_url": (MONEY_NET_BASE_URL or "https://api.money.net").rstrip("/"),
            "timeout": MONEY_NET_TIMEOUT_SEC,
        }
    except ImportError:
        return {"api_key": "", "base_url": "", "timeout": 15}


def is_available() -> bool:
    """Czy Money.net jest skonfigurowany (klucz API)."""
    cfg = _config()
    return bool(cfg.get("api_key") and str(cfg["api_key"]).strip())


def get_global_yields() -> Optional[Dict[str, Any]]:
    """
    Pobiera globalne stopy 10Y (US, DE, UK, JP, etc.) z Money.net.
    Zwraca np. {"US": 4.1, "DE": 2.2, "UK": 4.0, "JP": 0.9, "timestamp": "..."}
    lub None przy braku klucza / bledzie API.

    Po otrzymaniu dokumentacji API: dopasuj _fetch_yields() – endpoint i format odpowiedzi.
    """
    if not is_available():
        return None
    return _fetch_yields()


def _fetch_yields() -> Optional[Dict[str, Any]]:
    """
    Wlasciwe wywolanie API. Placeholder – po zalogowaniu do Money.net
    sprawdz dokumentacje (np. endpoint typu /market/rates lub /yields)
    i podmien url + parsowanie response.
    """
    import requests
    cfg = _config()
    api_key = cfg["api_key"].strip()
    base = cfg["base_url"]
    timeout = cfg.get("timeout", 15)

    # Placeholder: typowe warianty autoryzacji
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    # Jesli Money.net uzywa X-API-Key, odkomentuj i uzyj:
    # headers["X-API-Key"] = api_key

    # Placeholder URL – w dokumentacji sprawdz np.:
    #   /v1/market/yields
    #   /v1/rates/government
    #   /market/data/yields
    url = f"{base}/v1/market/yields"

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()

        # Placeholder: dopasuj do rzeczywistej struktury odpowiedzi.
        # Przyklad: data = {"yields": [{"country": "US", "value": 4.1}, ...]}
        # lub data = {"US10Y": 4.1, "DE10Y": 2.2, ...}
        if isinstance(data, dict):
            out = _parse_yields_response(data)
            if out:
                from datetime import datetime
                out["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                return out
        return None
    except Exception:
        return None


def _parse_yields_response(data: dict) -> Optional[Dict[str, Any]]:
    """
    Parsuje odpowiedz API na slownik kraj -> yield (10Y).
    Mapowanie nazw krajow: US, DE, UK, JP, CH, IT, ES, CN – do uzupelnienia wg API.
    """
    # Przyklady mozliwych formatow (odkomentuj i dostosuj po otrzymaniu docs):
    #
    # Format A: {"US": 4.1, "DE": 2.2, "UK": 4.0, "JP": 0.9}
    # if all(k in data for k in ("US", "DE")):
    #     return {k: float(v) for k, v in data.items() if k in ("US", "DE", "UK", "JP", "CH", "IT", "ES", "CN") and isinstance(v, (int, float))}
    #
    # Format B: {"series": [{"symbol": "US10Y", "value": 4.1}, ...]}
    # series = data.get("series") or data.get("yields") or []
    # out = {}
    # for s in series:
    #     sym = (s.get("symbol") or s.get("country") or "").upper()
    #     if "US" in sym or sym == "US10Y": out["US"] = float(s.get("value", 0))
    #     elif "DE" in sym or "GER" in sym: out["DE"] = float(s.get("value", 0))
    #     ...
    #     return out
    #
    return None
