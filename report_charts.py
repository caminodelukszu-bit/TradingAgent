# =============================================================================
# report_charts.py - Generowanie wykresów cenowych do raportu PDF (instytucjonalny styl)
# =============================================================================

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from io import BytesIO

# Mapowanie par CFD/FX na ticker yfinance
PAIR_TO_TICKER = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
    "XAU/USD": "GC=F",
    "XAG/USD": "SI=F",
    "BTC/USD": "BTC-USD",
    "BTC/USD (USDT)": "BTC-USD",
}


def _normalize_pair(para: str) -> str:
    """Zwraca znormalizowaną nazwę pary (np. z workflow 'Long EUR/USD' -> EUR/USD)."""
    if not para:
        return ""
    for p in PAIR_TO_TICKER:
        if p in para or para.strip().upper().endswith(p.replace("/", "")):
            return p
    if "/" in para:
        return para.strip()
    return para.strip() + "/USD" if para.strip() in ("EUR", "GBP", "AUD", "CAD", "CHF", "JPY") else ""


def get_ticker_for_pair(para: str) -> Optional[str]:
    """Zwraca ticker yfinance dla pary (np. EUR/USD -> EURUSD=X)."""
    norm = _normalize_pair(para)
    return PAIR_TO_TICKER.get(norm)


def render_chart_png(
    pair_label: str,
    yf_ticker: str,
    days: int = 30,
    width_inches: float = 5.0,
    height_inches: float = 2.2,
    title: Optional[str] = None,
) -> Optional[bytes]:
    """
    Renderuje wykres ceny zamykającej (days) do PNG. Zwraca bytes lub None przy błędzie.
    Styl: ciemne tło, linia ceny, minimalna legenda – jak w raportach instytucjonalnych.
    """
    try:
        import yfinance as yf
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        return None
    try:
        end = datetime.now()
        start = end - timedelta(days=days + 5)
        df = yf.download(
            yf_ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty or "Close" not in df.columns:
            return None
        series = df["Close"].dropna()
        if len(series) < 2:
            return None
        fig, ax = plt.subplots(figsize=(width_inches, height_inches), facecolor="#1a1d24")
        ax.set_facecolor("#1a1d24")
        ax.plot(series.index, series.values, color="#4285f4", linewidth=1.8, label="Close")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax.tick_params(colors="#9aa0a6", labelsize=8)
        ax.yaxis.tick_right()
        ax.spines["left"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.set_title(title or pair_label, color="#fafafa", fontsize=10, pad=6)
        ax.legend(loc="upper left", fontsize=7, facecolor="#25282e", edgecolor="#2d3136", labelcolor="#fafafa")
        ax.grid(True, alpha=0.2, color="#2d3136")
        fig.tight_layout(pad=0.8)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1d24", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def render_charts_for_workflow(
    workflow_top: List[dict],
    max_charts: int = 4,
    days: int = 30,
) -> List[Tuple[str, bytes]]:
    """
    Dla listy elementów workflow (słowniki z kluczem 'para') generuje wykresy.
    Zwraca listę (pair_label, png_bytes) – tylko udane.
    """
    seen = set()
    out = []
    for line in (workflow_top or [])[: max_charts + 2]:
        para = (line.get("para") or line.get("co") or "").strip()
        if not para or para in seen:
            continue
        # np. "Long EUR/USD" -> extract EUR/USD
        for known in PAIR_TO_TICKER:
            if known in para:
                para = known
                break
        ticker = get_ticker_for_pair(para)
        if not ticker or para in seen:
            continue
        seen.add(para)
        png = render_chart_png(para, ticker, days=days, title=para)
        if png:
            out.append((para, png))
        if len(out) >= max_charts:
            break
    return out
