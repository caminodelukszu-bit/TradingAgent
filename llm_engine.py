# =============================================================================
# llm_engine.py - SofikaMax Agent
# Wywolania LLM (OpenAI / Azure / Ollama). Few-shot, timeout, fallback.
# =============================================================================

from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Konfiguracja ladowana leniwie (unikanie importu config przy ladowaniu modulu)
def _config():
    from config import (
        LLM_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        LLM_MAX_TOKENS,
        LLM_TIMEOUT_SEC,
    )
    return {
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL or None,
        "model": LLM_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "timeout": LLM_TIMEOUT_SEC,
    }


def is_available() -> bool:
    """Czy LLM jest skonfigurowany i mozna go uzyc (klucz API + biblioteka)."""
    if OpenAI is None:
        return False
    cfg = _config()
    return bool(cfg["api_key"] and cfg["api_key"].strip())


def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: Optional[int] = None,
    timeout_sec: Optional[float] = None,
) -> Optional[str]:
    """
    Generuje odpowiedz LLM. Zwraca tekst lub None przy bledzie / braku konfiguracji.
    """
    if not is_available():
        return None
    cfg = _config()
    max_tok = max_tokens if max_tokens is not None else cfg["max_tokens"]
    timeout = timeout_sec if timeout_sec is not None else cfg["timeout"]

    client_kw = {"api_key": cfg["api_key"]}
    if cfg["base_url"]:
        client_kw["base_url"] = cfg["base_url"]

    try:
        client = OpenAI(**client_kw)
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tok,
            timeout=timeout,
        )
        choice = resp.choices[0] if resp.choices else None
        if choice and getattr(choice, "message", None):
            text = choice.message.content
            return (text or "").strip() or None
        return None
    except Exception:
        return None
