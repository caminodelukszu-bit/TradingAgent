# =============================================================================
# report_cache.py - Cache ostatniego pelnego raportu (wyniki, makro, payload)
# Uzywane przez Dashboard do automatycznego zaladowania raportu z harmonogramu
# (07:00, 12:30, 18:30, 20:30) bez klikania "Odswiez raport".
# =============================================================================

import os
import pickle
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(_SCRIPT_DIR, "data", "last_report_cache.pkl")
# Raport starszy niz MAX_AGE_HOURS nie bedzie auto-ladowany w dashboardzie
MAX_AGE_HOURS = 6


def save_report_cache(wyniki: List, makro: Dict, payload: Dict) -> None:
    """Zapisuje pelny raport do pliku (wywolywane przy wysylce na Telegram / scheduler)."""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    now = datetime.now()
    data = {
        "timestamp": now.isoformat(),
        "report_date": now.strftime("%Y-%m-%d"),
        "report_time": now.strftime("%H:%M"),
        "wyniki": wyniki,
        "makro": makro,
        "payload": payload,
    }
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_report_cache(max_age_hours: float = MAX_AGE_HOURS) -> Optional[Tuple[List, Dict, Dict]]:
    """
    Odczytuje ostatni zapisany raport. Zwraca (wyniki, makro, payload) lub None
    jesli brak cache lub raport jest starszy niz max_age_hours.
    """
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "rb") as f:
            data = pickle.load(f)
    except Exception:
        return None
    ts_str = data.get("timestamp")
    if not ts_str:
        return None
    try:
        cached_at = datetime.fromisoformat(ts_str)
    except Exception:
        return None
    age_hours = (datetime.now() - cached_at).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None
    wyniki = data.get("wyniki", [])
    makro = data.get("makro", {})
    payload = data.get("payload", {})
    return (wyniki, makro, payload)


def get_report_cache_meta() -> Optional[Dict[str, Any]]:
    """Zwraca metadane cache (timestamp, report_date, report_time) bez ladowania pelnego payloadu."""
    if not os.path.isfile(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "rb") as f:
            data = pickle.load(f)
    except Exception:
        return None
    return {
        "timestamp": data.get("timestamp"),
        "report_date": data.get("report_date"),
        "report_time": data.get("report_time"),
    }
