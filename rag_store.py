# =============================================================================
# rag_store.py - SofikaMax Agent
# Magazyn kontekstu pod RAG: raporty, feedback, weryfikacje. Retrieval po czasie.
# Bez embeddingów w v1 – ostatnie N wpisów jako kontekst dla LLM.
# =============================================================================

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

RAG_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag.db")


def _conn():
    return sqlite3.connect(RAG_DB)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                meta TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON rag_documents(source)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_rag_created ON rag_documents(created_at DESC)")


def add(source: str, content: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Dodaje dokument do RAG. source: report | feedback | outcome. Zwraca id."""
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_str = json.dumps(meta, ensure_ascii=False) if meta else None
    with _conn() as c:
        c.execute(
            "INSERT INTO rag_documents (source, content, meta, created_at) VALUES (?, ?, ?, ?)",
            (source, content, meta_str, now),
        )
        return c.lastrowid or 0


def add_report(report_date: str, summary: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Skrót: dodaje podsumowanie raportu."""
    return add("report", summary, (meta or {}) | {"report_date": report_date})


def add_feedback(summary: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Skrót: dodaje podsumowanie analizy feedbacku (co działa / nie działa)."""
    return add("feedback", summary, meta)


def add_outcomes(summary: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Skrót: dodaje podsumowanie weryfikacji sygnałów."""
    return add("outcome", summary, meta)


def add_claude_insight(summary: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Skrót: dodaje analizę Claude (historia) do RAG – do kontekstu w kolejnych raportach."""
    return add("claude_insight", summary, meta)


def get_recent(
    limit: int = 12,
    sources: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Ostatnie dokumenty, opcjonalnie filtrowane po source. Kolejność: najnowsze first."""
    init_db()
    with _conn() as c:
        c.row_factory = sqlite3.Row
        if sources:
            placeholders = ",".join("?" * len(sources))
            c.execute(
                f"""
                SELECT id, source, content, meta, created_at
                FROM rag_documents
                WHERE source IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*sources, limit),
            )
        else:
            c.execute(
                """
                SELECT id, source, content, meta, created_at
                FROM rag_documents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = c.fetchall()
    out = []
    for r in rows:
        meta = json.loads(r["meta"]) if r["meta"] else {}
        out.append({
            "id": r["id"],
            "source": r["source"],
            "content": r["content"],
            "meta": meta,
            "created_at": r["created_at"],
        })
    return out


def get_context_for_llm(limit: int = 12) -> str:
    """
    Zwraca jeden blok tekstu do wklejenia w prompt LLM:
    ostatnie raporty, feedback i outcomes. Format: [source] created_at -> content.
    """
    docs = get_recent(limit=limit)
    if not docs:
        return ""
    parts = []
    for d in docs:
        label = {"report": "Raport", "feedback": "Feedback", "outcome": "Weryfikacja", "claude_insight": "Claude (historia)"}.get(
            d["source"], d["source"]
        )
        parts.append(f"[{label} {d['created_at']}]\n{d['content']}")
    return "\n\n---\n\n".join(parts)
