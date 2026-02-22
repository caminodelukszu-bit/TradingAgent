# =============================================================================
# subscription_store.py - SofikaMax Agent
# Baza subskrybentow: kto dostaje raporty na Telegram. Pelna kontrola (wlacz/wylacz, data).
# SQLite - jeden plik, dziala na wielu komputerach przy wspoldzielonym pliku.
# =============================================================================

import os
import sqlite3
import secrets
from datetime import datetime
from typing import List, Optional, Tuple

try:
    from config import SUBSCRIPTION_DB_PATH
except ImportError:
    SUBSCRIPTION_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscriptions.db")
# Sciezka wzgledna -> w katalogu projektu
if not os.path.isabs(SUBSCRIPTION_DB_PATH):
    SUBSCRIPTION_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), SUBSCRIPTION_DB_PATH)


def _conn():
    return sqlite3.connect(SUBSCRIPTION_DB_PATH)


def init_db():
    """Tworzy tabele jesli nie istnieje."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                valid_until TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sub_active ON subscribers(active)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sub_valid ON subscribers(valid_until)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_tokens (
                token TEXT PRIMARY KEY,
                name TEXT,
                valid_until TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)


def get_active_subscribers() -> List[int]:
    """
    Zwraca liste telegram_id osob z aktywna subskrypcja:
    active=1 oraz (valid_until IS NULL lub valid_until >= dzisiaj).
    """
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    with _conn() as c:
        rows = c.execute("""
            SELECT telegram_id FROM subscribers
            WHERE active = 1 AND (valid_until IS NULL OR date(valid_until) >= date(?))
            ORDER BY telegram_id
        """, (today,)).fetchall()
    return [r[0] for r in rows]


def list_all() -> List[dict]:
    """Wszyscy subskrybenci (do panelu admina)."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT telegram_id, name, email, valid_until, active, created_at, updated_at
            FROM subscribers ORDER BY created_at DESC
        """).fetchall()
    return [
        {
            "telegram_id": r[0],
            "name": r[1] or "",
            "email": r[2] or "",
            "valid_until": r[3],
            "active": bool(r[4]),
            "created_at": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]


def add_subscriber(
    telegram_id: int,
    name: str = "",
    email: str = "",
    valid_until: Optional[str] = None,
) -> Tuple[bool, str]:
    """Dodaje lub aktualizuje subskrybenta. Zwraca (sukces, komunikat)."""
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with _conn() as c:
            c.execute("""
                INSERT INTO subscribers (telegram_id, name, email, valid_until, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    name = excluded.name,
                    email = excluded.email,
                    valid_until = excluded.valid_until,
                    active = 1,
                    updated_at = excluded.updated_at
            """, (telegram_id, (name or "").strip(), (email or "").strip(), valid_until or None, now, now))
        return True, "Dodano lub odnowiono subskrypcję."
    except Exception as e:
        return False, str(e)


def set_active(telegram_id: int, active: bool) -> Tuple[bool, str]:
    """Wlacza lub wylacza subskrypcje (natychmiastowy efekt)."""
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with _conn() as c:
            c.execute(
                "UPDATE subscribers SET active = ?, updated_at = ? WHERE telegram_id = ?",
                (1 if active else 0, now, telegram_id),
            )
            if c.rowcount == 0:
                return False, "Nie znaleziono subskrybenta."
        return True, "Subskrypcja włączona." if active else "Subskrypcja wyłączona."
    except Exception as e:
        return False, str(e)


def set_valid_until(telegram_id: int, valid_until: Optional[str]) -> Tuple[bool, str]:
    """Ustawia date waznosci (YYYY-MM-DD). None = bez limitu."""
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with _conn() as c:
            c.execute(
                "UPDATE subscribers SET valid_until = ?, updated_at = ? WHERE telegram_id = ?",
                (valid_until, now, telegram_id),
            )
            if c.rowcount == 0:
                return False, "Nie znaleziono subskrybenta."
        return True, "Data ważności zaktualizowana."
    except Exception as e:
        return False, str(e)


def remove_subscriber(telegram_id: int) -> Tuple[bool, str]:
    """Usuwa subskrybenta z bazy (trwale)."""
    init_db()
    try:
        with _conn() as c:
            c.execute("DELETE FROM subscribers WHERE telegram_id = ?", (telegram_id,))
            if c.rowcount == 0:
                return False, "Nie znaleziono subskrybenta."
        return True, "Subskrybent usunięty."
    except Exception as e:
        return False, str(e)


def import_from_list(telegram_ids: List[int], default_name: str = "Subskrybent") -> Tuple[int, str]:
    """
    Importuje liste telegram_id do bazy (active=1, bez daty konca).
    Zwraca (liczba dodanych, komunikat).
    """
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    added = 0
    try:
        with _conn() as c:
            for tid in telegram_ids:
                if not tid:
                    continue
                c.execute("""
                    INSERT INTO subscribers (telegram_id, name, valid_until, active, created_at, updated_at)
                    VALUES (?, ?, NULL, 1, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET active = 1, valid_until = NULL, updated_at = ?
                """, (tid, default_name, now, now, now))
                added += 1
        return added, f"Zaimportowano {added} subskrybentów."
    except Exception as e:
        return 0, str(e)


# ============== DASHBOARD – czasowy dostęp (tokeny) ==============

def create_dashboard_token(name: str = "", valid_until: Optional[str] = None) -> Tuple[str, str]:
    """Tworzy token dostępu do Dashboard. Zwraca (token, komunikat). Token przekaż gościowi – wchodzi do platformy do valid_until."""
    init_db()
    token = secrets.token_urlsafe(24)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with _conn() as c:
            c.execute("""
                INSERT INTO dashboard_tokens (token, name, valid_until, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (token, (name or "").strip(), valid_until or None, now))
        return token, "Token utworzony. Przekaż gościowi link i token (ważny do: " + (valid_until or "bez limitu") + ")."
    except Exception as e:
        return "", str(e)


def revoke_dashboard_token(token: str) -> Tuple[bool, str]:
    """Unieważnia token – gość traci dostęp natychmiast."""
    init_db()
    try:
        with _conn() as c:
            c.execute("DELETE FROM dashboard_tokens WHERE token = ?", (token,))
            if c.rowcount == 0:
                return False, "Nie znaleziono tokenu."
        return True, "Token unieważniony."
    except Exception as e:
        return False, str(e)


def list_dashboard_tokens() -> List[dict]:
    """Lista wszystkich tokenów (do panelu admina)."""
    init_db()
    with _conn() as c:
        rows = c.execute("""
            SELECT token, name, valid_until, active, created_at FROM dashboard_tokens ORDER BY created_at DESC
        """).fetchall()
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "token": r[0],
            "name": r[1] or "",
            "valid_until": r[2],
            "active": bool(r[3]),
            "created_at": r[4],
            "valid": (r[2] is None or r[2] >= today) and r[3],
        }
        for r in rows
    ]


def check_dashboard_token(token: str) -> bool:
    """Sprawdza czy token jest ważny (aktywny i nie przekroczona data)."""
    if not (token and token.strip()):
        return False
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    with _conn() as c:
        row = c.execute("""
            SELECT 1 FROM dashboard_tokens
            WHERE token = ? AND active = 1 AND (valid_until IS NULL OR date(valid_until) >= date(?))
        """, (token.strip(), today)).fetchone()
    return row is not None


if __name__ == "__main__":
    init_db()
    print("Subskrybenci aktywni:", get_active_subscribers())
    print("Wszyscy:", list_all())
