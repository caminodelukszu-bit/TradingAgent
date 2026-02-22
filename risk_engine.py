# =============================================================================
# risk_engine.py - SofikaMax Agent
# Warstwa ryzyka portfela: ekspozycja grupowa, max pozycje, rekomendacje.
# Limity instytucjonalne (exposure control) – banki/fundusze.
# Nie zmienia scoringu – dostarcza metadane do raportu i dashboardu.
# =============================================================================

from typing import List, Dict, Any, Optional

try:
    from config import (
        MAX_POSITIONS_TOTAL,
        MAX_POSITIONS_IN_GROUP,
        MAX_EXPOSURE_PCT_CURRENCY,
    )
except ImportError:
    MAX_POSITIONS_TOTAL = 5
    MAX_POSITIONS_IN_GROUP = 2
    MAX_EXPOSURE_PCT_CURRENCY = 10


def _instrument_z_pary(para: str, nazwa_do_inst: dict) -> str:
    """Z nazwy pary (XAU/USD, EUR/USD) zwraca symbol instrumentu."""
    if para in nazwa_do_inst:
        return nazwa_do_inst[para]
    if "/" in para:
        return para.split("/")[0]
    return para


def _aktywne_bias(w: dict) -> bool:
    """Czy instrument ma aktywny sygnał (KUP/SPRZEDAJ) powyżej progu."""
    return w.get("bias") in ("KUP", "SPRZEDAJ") and w.get("conviction") != "PASS"


def oblicz_ryzyko_portfela(
    wyniki: List[Dict[str, Any]],
    pary_cross: List[Dict[str, Any]],
    pary_usd: List[Dict[str, Any]],
    grupy_korelacyjne: Dict[str, List[str]],
    max_pozycje_domyslnie: int | None = None,
    max_pozycje_w_grupie: int | None = None,
) -> Dict[str, Any]:
    """
    Oblicza metryki ryzyka portfela na podstawie wyników i par.
    Używa limitów z config (MAX_POSITIONS_*, MAX_EXPOSURE_PCT_CURRENCY) gdy nie podano.

    Zwraca:
        max_pozycje: rekomendowana max liczba otwartych pozycji
        exposure: { "SUROWCE": ["AUD", "CAD"], ... } – które instrumenty z danej grupy są w sygnałach
        ostrzezenia: lista tekstów do wyświetlenia
        rekomendacja: jedna linia podsumowania
        ok: czy brak przekroczeń
    """
    if max_pozycje_domyslnie is None:
        max_pozycje_domyslnie = MAX_POSITIONS_TOTAL
    if max_pozycje_w_grupie is None:
        max_pozycje_w_grupie = MAX_POSITIONS_IN_GROUP
    nazwa_do_inst = {"XAU/USD": "GOLD", "XAG/USD": "SILVER", "BTC/USD (USDT)": "BTC"}
    instrumenty_w_parach = set()

    for p in pary_cross[:12]:
        inst = _instrument_z_pary(p.get("para", ""), nazwa_do_inst)
        if inst:
            instrumenty_w_parach.add(inst)
    for p in pary_usd[:12]:
        para = p.get("para", "")
        inst = nazwa_do_inst.get(para, para.split("/")[0] if "/" in para else "")
        if inst:
            instrumenty_w_parach.add(inst)

    # Aktywne sygnały z wyników (conviction nie PASS)
    aktywne = [w for w in wyniki if _aktywne_bias(w)]
    aktywne_instruments = {w["instrument"] for w in aktywne}

    # Ekspozycja per grupa
    exposure: Dict[str, List[str]] = {}
    for grupa, instrumenty in grupy_korelacyjne.items():
        w_grupie = [i for i in instrumenty if i in instrumenty_w_parach or i in aktywne_instruments]
        if w_grupie:
            exposure[grupa] = sorted(w_grupie)

    # Ostrzeżenia
    ostrzezenia: List[str] = []
    for grupa, lista in exposure.items():
        n = len(lista)
        if n > max_pozycje_w_grupie:
            ostrzezenia.append(
                f"{grupa}: {n} sygnały – rekomendacja max {max_pozycje_w_grupie} pozycje w tej samej grupie."
            )
        elif n == max_pozycje_w_grupie:
            ostrzezenia.append(
                f"{grupa}: {n} sygnały ({', '.join(lista)}) – nie dodawaj kolejnej pozycji w tej grupie."
            )

    # Max pozycje: ogranicz jeśli dużo sygnałów z tych samych grup
    n_aktywnych = len(aktywne_instruments)
    n_par = len([p for p in pary_cross + pary_usd if p.get("sila_sygnalu", 0) >= 15][:10])
    max_pozycje = min(max_pozycje_domyslnie, max(n_par, n_aktywnych))
    max_pozycje = max(2, min(6, max_pozycje))

    ok = len(ostrzezenia) == 0
    exposure_note = f" Max {MAX_EXPOSURE_PCT_CURRENCY}% kapitału łącznie na jedną walutę."
    if ok:
        rekomendacja = (
            f"Rekomendacja: max {max_pozycje} równoczesnych pozycji, max {max_pozycje_w_grupie} w grupie."
            + exposure_note
            + " Rozkład ekspozycji w normie."
        )
    else:
        rekomendacja = (
            f"Rekomendacja: max {max_pozycje} pozycji, max {max_pozycje_w_grupie} w grupie."
            + exposure_note
            + " Uwaga: ogranicz ekspozycję w grupach korelacyjnych."
        )

    return {
        "max_pozycje": max_pozycje,
        "exposure": exposure,
        "ostrzezenia": ostrzezenia,
        "rekomendacja": rekomendacja,
        "ok": ok,
        "n_aktywne_sygnaly": n_aktywnych,
        "n_par_w_raporcie": len(pary_cross) + len(pary_usd),
    }
