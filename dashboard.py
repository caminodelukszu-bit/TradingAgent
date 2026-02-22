# =============================================================================
# dashboard.py - SofikaMax Trading Desk (kursy, wykresy, raport narracyjny)
# Uruchomienie: streamlit run dashboard.py  |  http://localhost:8501
# =============================================================================

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Ścieżka do logo SofikaMax (białe logo na czarnym – w nagłówku i w ikonie zakładki)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_SCRIPT_DIR, "assets", "sofikamax_logo.png")
# Opcjonalnie: logo zapisane w Cursor (assets) – fallback
LOGO_PATH_FALLBACK = os.path.join(_SCRIPT_DIR, "assets", "SOFIKAMAX_LOGO-ce739085-6d0c-484c-a54a-0e960e2cffa8.png")
def _logo_path():
    if os.path.isfile(LOGO_PATH):
        return LOGO_PATH
    if os.path.isfile(LOGO_PATH_FALLBACK):
        return LOGO_PATH_FALLBACK
    return None

try:
    from config import ADMIN_PASSWORD, DASHBOARD_REQUIRE_TOKEN
except ImportError:
    ADMIN_PASSWORD = ""
    DASHBOARD_REQUIRE_TOKEN = False

# Konfiguracja strony – Trading Desk (ikona zakładki = logo SofikaMax, jeśli jest)
_logo = _logo_path()
st.set_page_config(
    page_title="SofikaMax Trading Desk",
    page_icon=_logo if _logo else "▣",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ciemny styl – poziom NIL (Narrative Intelligence)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1, h2, h3 { color: #fafafa; font-weight: 600; }
    .report-meta { color: #9aa0a6; font-size: 0.95rem; margin-bottom: 1rem; }
    .metric-card { background: #1a1d24; padding: 1rem 1.25rem; border-radius: 10px; margin: 0.5rem 0; border-left: 4px solid #4285f4; }
    .metric-card.green { border-left-color: #0f9d58; }
    .metric-card.orange { border-left-color: #f9ab00; }
    .metric-card.red { border-left-color: #ea4335; }
    .badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
    .badge-long { background: #0f9d58; color: #fff; }
    .badge-short { background: #ea4335; color: #fff; }
    .badge-neut { background: #5f6368; color: #fff; }
    .badge-high { background: #0f9d58; color: #fff; }
    .badge-mod { background: #f9ab00; color: #0e1117; }
    .badge-low { background: #5f6368; color: #fff; }
    .badge-event { background: #9c27b0; color: #fff; }
    .decision-box { padding: 1rem 1.25rem; border-radius: 10px; margin: 1rem 0; font-weight: 600; }
    .decision-go { background: rgba(15,157,88,0.2); border: 1px solid #0f9d58; color: #81c995; }
    .decision-caution { background: rgba(249,171,0,0.2); border: 1px solid #f9ab00; color: #fdd663; }
    .decision-no { background: rgba(234,67,53,0.2); border: 1px solid #ea4335; color: #f28b82; }
    .progress-wrap { background: #2d3136; border-radius: 8px; height: 8px; overflow: hidden; margin: 0.25rem 0; }
    .progress-fill { height: 100%; border-radius: 8px; transition: width 0.3s; }
    .cycle-card { background: #1a1d24; padding: 1rem; border-radius: 10px; margin: 0.5rem 0; border-left: 4px solid #5f6368; }
    .cycle-card.expansion { border-left-color: #0f9d58; }
    .cycle-card.slowdown { border-left-color: #f9ab00; }
    .cycle-card.contraction { border-left-color: #ea4335; }
    .section-title { color: #fafafa; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin: 1.25rem 0 0.5rem 0; }
    div[data-testid="stDataFrame"] { background: #1a1d24; border-radius: 8px; }
    div[data-testid="stExpander"] { background: #1a1d24; border-radius: 8px; }
    .desk-header { display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0 1rem 0; border-bottom: 1px solid #2d3136; margin-bottom: 1rem; }
    .desk-title { font-size: 1.25rem; font-weight: 700; color: #fafafa; letter-spacing: 0.02em; }
    .desk-clock { font-family: monospace; color: #9aa0a6; font-size: 0.9rem; }
    .ticker-bar { display: flex; flex-wrap: wrap; gap: 0.75rem; padding: 0.6rem 0; background: #1a1d24; border-radius: 8px; margin-bottom: 1rem; border: 1px solid #2d3136; }
    .ticker-item { padding: 0.35rem 0.75rem; border-radius: 6px; background: #25282e; font-family: monospace; }
    .ticker-pair { color: #9aa0a6; font-size: 0.75rem; }
    .ticker-price { color: #fafafa; font-size: 1rem; font-weight: 600; }
    .ticker-change { font-size: 0.75rem; }
    .ticker-change.up { color: #0f9d58; }
    .ticker-change.down { color: #ea4335; }
    .chart-container { background: #1a1d24; border-radius: 10px; padding: 1rem; margin: 0.5rem 0; border: 1px solid #2d3136; }
    .desk-logo { height: 36px; margin-right: 0.75rem; vertical-align: middle; object-fit: contain; }
</style>
""", unsafe_allow_html=True)

# Pary do paska kursów i wykresów (label, ticker yfinance)
DESK_RATES = [
    ("EUR/USD", "EURUSD=X"),
    ("GBP/USD", "GBPUSD=X"),
    ("USD/JPY", "USDJPY=X"),
    ("AUD/USD", "AUDUSD=X"),
    ("XAU/USD", "GC=F"),
    ("XAG/USD", "SI=F"),
    ("BTC/USD", "BTC-USD"),
]


@st.cache_data(ttl=60)
def _fetch_live_rates():
    """Pobiera aktualne kursy (cache 60 s). Zwraca listę {pair, price, change_pct}."""
    import yfinance as yf
    out = []
    for label, ticker in DESK_RATES:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist is not None and len(hist) >= 2:
                close = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                ch = ((close - prev) / prev * 100) if prev else 0
                out.append({"pair": label, "price": close, "change_pct": ch})
            elif len(hist) == 1:
                out.append({"pair": label, "price": float(hist["Close"].iloc[-1]), "change_pct": 0})
            else:
                out.append({"pair": label, "price": None, "change_pct": None})
        except Exception:
            out.append({"pair": label, "price": None, "change_pct": None})
    return out


@st.cache_data(ttl=120)
def _fetch_chart_data(ticker: str, days: int = 30):
    """Pobiera dane do wykresu (cache 2 min). Zwraca DataFrame z kolumną Close i indeksem dat."""
    import yfinance as yf
    try:
        end = datetime.now()
        start = end - timedelta(days=days + 5)
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
        if df is not None and not df.empty and "Close" in df.columns:
            return df[["Close"]].rename(columns={"Close": "close"}).reset_index()
    except Exception:
        pass
    return pd.DataFrame()


def _render_ticker_bar():
    """Renderuje pasek kursów nad treścią."""
    rates = _fetch_live_rates()
    items = []
    for r in rates:
        if r["price"] is not None:
            price_str = f"{r['price']:.5f}" if r["price"] < 1 or r["pair"] == "BTC/USD" else f"{r['price']:,.2f}"
            ch = r.get("change_pct")
            if ch is not None:
                cls = "up" if ch >= 0 else "down"
                ch_str = f"{ch:+.2f}%"
            else:
                cls, ch_str = "", "–"
            items.append(
                f'<span class="ticker-item">'
                f'<span class="ticker-pair">{r["pair"]}</span> '
                f'<span class="ticker-price">{price_str}</span> '
                f'<span class="ticker-change {cls}">{ch_str}</span></span>'
            )
        else:
            items.append(f'<span class="ticker-item"><span class="ticker-pair">{r["pair"]}</span> <span class="ticker-price">–</span></span>')
    st.markdown(f'<div class="ticker-bar">{" ".join(items)}</div>', unsafe_allow_html=True)


def _render_rates_and_charts(key_prefix: str = ""):
    """Sekcja Rates & Charts – wykresy liniowe (plotly) dla kilku par. Gdy brak plotly: tabela kursów. key_prefix zapewnia unikalne key przy wielokrotnym wywolaniu (strona glowna + zakladka)."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        has_plotly = True
    except ImportError:
        has_plotly = False
    if not has_plotly:
        st.caption("Wykresy: zainstaluj plotly (`pip install plotly`). Poniżej aktualne kursy.")
        rates = _fetch_live_rates()
        rows = [{"Para": r["pair"], "Kurs": f"{r['price']:.5g}" if r.get("price") else "–", "Zmiana %": f"{r.get('change_pct', 0):+.2f}%" if r.get("change_pct") is not None else "–"} for r in rates]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return
    charts = [("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"), ("XAU/USD", "GC=F"), ("BTC/USD", "BTC-USD")]
    cols = st.columns(2)
    for i, (label, ticker) in enumerate(charts):
        df = _fetch_chart_data(ticker, days=30)
        with cols[i % 2]:
            if df.empty or len(df) < 2:
                st.markdown(f'<div class="chart-container"><strong>{label}</strong><br><span style="color:#9aa0a6">Brak danych</span></div>', unsafe_allow_html=True)
                continue
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["Date"], y=df["close"], mode="lines", name=label, line=dict(color="#4285f4", width=2)))
            fig.update_layout(
                title=dict(text=label, font=dict(size=14)),
                margin=dict(l=40, r=20, t=40, b=40),
                height=220,
                paper_bgcolor="#1a1d24",
                plot_bgcolor="#1a1d24",
                font=dict(color="#fafafa", size=11),
                xaxis=dict(gridcolor="#2d3136", showgrid=True),
                yaxis=dict(gridcolor="#2d3136", showgrid=True),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False), key=f"{key_prefix}rates_chart_{label}")


def _render_subscription_admin():
    """Panel zarzadzania subskrypcjami (chroniony haslem)."""
    if not ADMIN_PASSWORD:
        st.warning("Ustaw ADMIN_PASSWORD w config.py, aby zarzadzac subskrypcjami.")
        return
    if st.session_state.get("admin_authenticated") is not True:
        pwd = st.text_input("Haslo administratora", type="password", key="admin_pwd")
        if st.button("Zaloguj"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Nieprawidlowe haslo.")
        return
    # Zalogowany admin
    st.success("Zalogowano jako administrator.")
    if st.button("Wyloguj", key="admin_logout"):
        st.session_state.admin_authenticated = False
        st.rerun()
    try:
        from subscription_store import list_all, add_subscriber, set_active, remove_subscriber, import_from_list
        from telegram_bot import AUTORYZOWANI
    except Exception as e:
        st.error(f"Blad: {e}")
        return
    subs = list_all()
    st.subheader("Lista subskrybentow")
    if not subs:
        st.info("Brak subskrybentow. Dodaj Telegram ID lub zaimportuj liste z config.")
    else:
        for s in subs:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            with col1:
                st.text(f"ID: {s['telegram_id']} | {s['name'] or '-'}")
            with col2:
                st.text(f"Email: {s['email'] or '-'} | Do: {s['valid_until'] or 'bez limitu'}")
            with col3:
                status = "Aktywny" if s['active'] else "Wylaczony"
                st.text(status)
            with col4:
                if st.button("Wlacz" if not s['active'] else "Wylacz", key=f"tog_{s['telegram_id']}"):
                    ok, msg = set_active(s['telegram_id'], not s['active'])
                    st.success(msg)
                    st.rerun()
            with col5:
                if st.button("Usun", key=f"del_{s['telegram_id']}"):
                    ok, msg = remove_subscriber(s['telegram_id'])
                    st.success(msg)
                    st.rerun()
        st.divider()
    st.subheader("Dodaj subskrybenta")
    with st.form("add_sub"):
        tid = st.number_input("Telegram ID (liczba)", min_value=0, step=1, key="new_tid")
        name = st.text_input("Imie / nazwa", key="new_name")
        valid = st.text_input("Wazny do (YYYY-MM-DD, puste = bez limitu)", key="new_valid")
        if st.form_submit_button("Dodaj"):
            if tid:
                ok, msg = add_subscriber(int(tid), name=name, valid_until=valid.strip() or None)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
                st.rerun()
            else:
                st.warning("Podaj Telegram ID.")
    st.subheader("Import z config")
    st.caption("Dodaj obecna liste AUTORYZOWANI z telegram_bot/config do bazy (jako aktywni, bez daty).")
    if st.button("Importuj AUTORYZOWANI do bazy"):
        n, msg = import_from_list(AUTORYZOWANI, default_name="Subskrybent")
        st.success(msg)
        st.rerun()

    st.divider()
    st.subheader("Dostęp do Dashboard (czasowy dla gości)")
    st.caption("Utwórz token i przekaż gościowi. Link do platformy + token. Ważność do wybranej daty lub bez limitu. Odwołanie: Revoke.")
    try:
        from subscription_store import (
            list_dashboard_tokens, create_dashboard_token, revoke_dashboard_token, check_dashboard_token
        )
    except Exception as e:
        st.error(f"Blad: {e}")
        return
    tokens = list_dashboard_tokens()
    if tokens:
        for i, t in enumerate(tokens):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.text(f"Token: {t['token'][:12]}... | {t['name'] or '–'} | do: {t['valid_until'] or 'bez limitu'}")
            with col2:
                st.caption("Ważny" if t["valid"] else "Wygasły / odwołany")
            with col3:
                if st.button("Revoke", key=f"rev_tok_{i}"):
                    ok, msg = revoke_dashboard_token(t["token"])
                    st.success(msg)
                    st.rerun()
        st.divider()
    with st.form("add_token"):
        tname = st.text_input("Nazwa gościa (opcjonalnie)", key="token_name")
        tvalid = st.text_input("Ważny do (YYYY-MM-DD, puste = bez limitu)", key="token_valid")
        if st.form_submit_button("Utwórz token dostępu"):
            tok, msg = create_dashboard_token(name=tname, valid_until=tvalid.strip() or None)
            if tok:
                st.success("Token utworzony. Skopiuj i przekaż gościowi (pokazujemy tylko raz):")
                st.code(tok, language=None)
                st.caption(msg)
            else:
                st.error(msg)
            st.rerun()


@st.cache_data(ttl=120)
def _get_quarter_analysis():
    """Analiza kwartalna (ostatnie 123 raporty) – cache 2 min."""
    try:
        from report_archive import get_reports_for_quarter
        from quarter_analysis import analyze_quarter_reports, QUARTER_REPORTS_LIMIT
        reports = get_reports_for_quarter(limit=QUARTER_REPORTS_LIMIT)
        return analyze_quarter_reports(reports)
    except Exception:
        return None


@st.cache_data(ttl=90)
def _get_latest_official_headlines(limit: int = 15):
    """Ostatnie komunikaty oficjalne (z bazy)."""
    try:
        from official_sources import get_latest
        return get_latest(limit=limit)
    except Exception:
        return []


def _render_home_platform():
    """
    Strona główna platformy – od razu po zalogowaniu: historia, analiza kwartalna,
    tabela raportów, kursy, wykresy, kalendarz, komunikaty oficjalne. Nie wymaga „Odśwież raport”.
    """
    st.markdown('<p class="section-title">Strona główna – podsumowanie platformy</p>', unsafe_allow_html=True)

    # Ostatni raport z archiwum + analiza kwartalna
    try:
        from report_archive import list_reports
        reports = list_reports(limit=20)
    except Exception:
        reports = []
    if reports:
        last = reports[0]
        dec = last.get("decision", "–")
        if "NIE WCHODŹ" in (dec or ""):
            box_class = "decision-no"
            dec_short = "CZEKAJ"
        elif "OGRANICZENIAMI" in (dec or ""):
            box_class = "decision-caution"
            dec_short = "Ostrożne wejście"
        else:
            box_class = "decision-go"
            dec_short = "Wejście"
        st.markdown(
            f'<div class="decision-box {box_class}">'
            f'📅 Ostatni raport: <strong>{last.get("report_date", "")} {last.get("report_time", "")}</strong> &nbsp; Decyzja: <strong>{dec_short}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info(
            "Brak raportów w archiwum. **Kliknij raz „Odśwież raport (pobierz dane)” w panelu bocznym (☰)** – "
            "po 1–2 min zobaczysz tu ostatni raport, tabelę i analizę. Raporty trafiają też do archiwum z harmonogramu (07:00 | 12:30 | 18:30 | 20:30)."
        )

    # Analiza kwartalna – karty + opis
    qa = _get_quarter_analysis()
    if qa and qa.get("n_reports", 0) > 0:
        st.markdown('<p class="section-title">Analiza kwartalna (ostatnie raporty pod kontrolą)</p>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Raportów w analizie", qa.get("n_reports", 0))
        with c2:
            dec = qa.get("decision_distribution") or {}
            czekaj_pct = round(100 * dec.get("CZEKAJ", 0) / qa["n_reports"]) if qa["n_reports"] else 0
            st.metric("% decyzji CZEKAJ", f"{czekaj_pct}%")
        with c3:
            st.metric("Seria CZEKAJ z rzędu", qa.get("streak_czekaj", 0))
        with c4:
            top = qa.get("top_instruments", [])[:3]
            st.metric("Najczęstsze rekomendacje", ", ".join(top) if top else "–")
        st.caption(qa.get("summary_paragraph_pl", ""))

    # Tabela ostatnich raportów
    st.markdown('<p class="section-title">Ostatnie raporty (tabela)</p>', unsafe_allow_html=True)
    if reports:
        rows = []
        for r in reports[:25]:
            s = r.get("summary") or {}
            sigs = s.get("signals", [])[:3]
            sig_str = ", ".join([f"{x.get('instrument')} {x.get('bias')}" for x in sigs if x.get("instrument")])
            rows.append({
                "Data": r.get("report_date", ""),
                "Godzina": r.get("report_time", ""),
                "Decyzja": (r.get("decision") or "")[:30],
                "Top sygnały": sig_str[:50],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Pełna lista i porównanie: zakładka **Archiwum raportów**.")
    else:
        st.caption("Brak danych. Kliknij **Odśwież raport (pobierz dane)** w panelu bocznym – po wygenerowaniu tabela wypełni się automatycznie.")

    # Kursy i wykresy
    st.markdown('<p class="section-title">Kursy i wykresy (30d)</p>', unsafe_allow_html=True)
    _render_rates_and_charts(key_prefix="home_")

    # Kalendarz nadchodzących wydarzeń
    st.markdown('<p class="section-title">Nadchodzące wydarzenia (kalendarz)</p>', unsafe_allow_html=True)
    try:
        from event_calendar import get_upcoming_events_summary
        ev = get_upcoming_events_summary(currency=None, days_ahead=7, max_events=10)
        if ev:
            st.caption(ev)
        else:
            st.caption("Brak wysokowagowych wydarzeń w najbliższych 7 dniach.")
    except Exception:
        st.caption("Kalendarz: sprawdź event_calendar.")

    # Komunikaty oficjalne (źródła rządowe / banki centralne)
    st.markdown('<p class="section-title">Komunikaty oficjalne (banki centralne, wybrane źródła)</p>', unsafe_allow_html=True)
    headlines = _get_latest_official_headlines(limit=15)
    if headlines:
        for h in headlines[:10]:
            st.markdown(f"**{h.get('source', '')}** ({h.get('region', '')}): [{h.get('title', '')[:70]}]({h.get('link', '#') or '#'})")
        if st.button("Pobierz najnowsze komunikaty", key="fetch_official"):
            try:
                from official_sources import fetch_and_store
                n = fetch_and_store()
                st.success(f"Pobrano i zapisano {n} komunikatów.")
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        st.caption("Brak zapisanych komunikatów. **Przy pierwszym wejściu** kliknij poniżej, aby pobrać komunikaty z ECB, FED, BOE, NBP (RSS) i wypełnić sekcję.")
        if st.button("Pobierz najnowsze komunikaty", key="fetch_official_first"):
            try:
                from official_sources import fetch_and_store
                n = fetch_and_store()
                st.success(f"Pobrano i zapisano {n} komunikatów.")
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.markdown(
        '<div class="metric-card">'
        '<strong>Pełny raport na żywo</strong><br>'
        'Jedno kliknięcie: <strong>Odśwież raport (pobierz dane)</strong> w panelu bocznym (☰) generuje pełną analizę COT, reżim, flow i rekomendacje oraz zapisuje raport do archiwum (ta strona od razu się wypełni).'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_report_archive():
    """Zakładka Archiwum raportów: wykresy historyczne, tabela, porównanie z poprzednim."""
    try:
        from report_archive import list_reports, get_report, get_two_for_comparison, diff_reports
    except ImportError:
        st.warning("Moduł report_archive niedostępny. Archiwum powstaje przy wysyłce raportu na Telegram.")
        return
    st.subheader("Archiwum raportów")
    st.caption("Raporty zapisywane przy każdej wysyłce. Wykresy: decyzja i makro w czasie. Porównanie: ciągłość z poprzednim.")
    reports = list_reports(limit=150)
    if not reports:
        st.info("Brak zapisanych raportów. Wyślij raport z harmonogramu (07:00 | 12:30 | 18:30 | 20:30) lub z main.py.")
        return

    # Wykresy historyczne z archiwum
    st.markdown('<p class="section-title">Decyzja w czasie (z archiwum)</p>', unsafe_allow_html=True)
    try:
        import plotly.graph_objects as go
        _norm = lambda d: "CZEKAJ" if d and "NIE WCHODŹ" in d.upper() else ("Ostrożnie" if d and "OGRANICZENIAMI" in d.upper() else "Wejście")
        df_dec = pd.DataFrame([
            {"data": r["report_date"], "godzina": r["report_time"], "decyzja": _norm(r.get("decision"))}
            for r in reports[:80]
        ])
        if not df_dec.empty:
            dec_counts = df_dec.groupby("decyzja").size().reset_index(name="count")
            fig = go.Figure(data=[go.Bar(x=dec_counts["decyzja"], y=dec_counts["count"], marker_color=["#ea4335", "#f9ab00", "#0f9d58"])])
            fig.update_layout(
                title="Rozkład decyzji (ostatnie raporty)", margin=dict(t=40, b=40), height=220,
                paper_bgcolor="#1a1d24", plot_bgcolor="#1a1d24", font=dict(color="#fafafa"),
                xaxis=dict(gridcolor="#2d3136"), yaxis=dict(gridcolor="#2d3136"),
            )
            st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False), key="archive_dec_chart")
        # Makro DXY / FED w czasie (z summary)
        macro_rows = []
        for r in reports[:60]:
            s = r.get("summary") or {}
            m = s.get("macro") or {}
            if m.get("DXY") is not None or m.get("FED") is not None:
                macro_rows.append({
                    "data": r["report_date"], "godzina": r["report_time"],
                    "DXY": m.get("DXY"), "FED": m.get("FED"),
                })
        if macro_rows:
            df_m = pd.DataFrame(macro_rows)
            df_m["datetime"] = pd.to_datetime(df_m["data"] + " " + df_m["godzina"], errors="coerce")
            df_m = df_m.dropna(subset=["datetime"]).sort_values("datetime")
            if len(df_m) >= 2:
                fig2 = go.Figure()
                if df_m["DXY"].notna().any():
                    fig2.add_trace(go.Scatter(x=df_m["datetime"], y=df_m["DXY"], name="DXY", line=dict(color="#4285f4")))
                if df_m["FED"].notna().any():
                    fig2.add_trace(go.Scatter(x=df_m["datetime"], y=df_m["FED"], name="FED %", line=dict(color="#f9ab00")))
                fig2.update_layout(
                    title="Makro (DXY, FED) z archiwum raportów", margin=dict(t=40, b=40), height=220,
                    paper_bgcolor="#1a1d24", plot_bgcolor="#1a1d24", font=dict(color="#fafafa"),
                    xaxis=dict(gridcolor="#2d3136"), yaxis=dict(gridcolor="#2d3136"), showlegend=True,
                )
                st.plotly_chart(fig2, use_container_width=True, config=dict(displayModeBar=False), key="archive_macro_chart")
    except Exception as e:
        st.caption("Wykresy z archiwum: " + str(e))

    # Tabela raportów (najnowsze u góry)
    st.markdown('<p class="section-title">Raporty (najnowsze u góry)</p>', unsafe_allow_html=True)
    for r in reports:
        with st.expander(f"📅 {r['report_date']} {r['report_time']}  |  Decyzja: {r.get('decision', '–')}"):
            summary = r.get("summary") or {}
            st.write("**Health:**", summary.get("health", "–"))
            sigs = summary.get("signals", [])
            if sigs:
                st.write("**Sygnały:**", ", ".join([f"{s.get('instrument')} {s.get('bias')} ({s.get('score')})" for s in sigs[:6]]))
            macro = summary.get("macro") or {}
            if macro:
                st.write("**Makro:**", " | ".join([f"{k}: {v}" for k, v in macro.items() if v is not None]))
            if summary.get("reasons"):
                st.caption("Powody: " + " | ".join(summary["reasons"][:2]))
            if summary.get("ryzyka"):
                st.caption("Ryzyka: " + " | ".join(summary["ryzyka"][:2]))
            compare_id = r["id"]
            if st.button("Porównaj z poprzednim", key=f"cmp_{compare_id}"):
                st.session_state.report_compare_id = compare_id
                st.rerun()
            if st.session_state.get("report_compare_id") == compare_id:
                curr, prev = get_two_for_comparison(compare_id)
                if curr and prev:
                    diff = diff_reports(curr, prev)
                    st.markdown("**Zestawienie zmian (ciągłość / różnice)**")
                    if diff["decision_changed"]:
                        st.warning(f"Decyzja: {diff['decision_prev']} → {diff['decision_curr']}")
                    if diff["signals_added"]:
                        st.success("Nowe sygnały: " + ", ".join(diff["signals_added"]))
                    if diff["signals_removed"]:
                        st.info("Usunięte sygnały: " + ", ".join(diff["signals_removed"]))
                    if diff["signals_changed"]:
                        for ch in diff["signals_changed"][:5]:
                            st.caption(f"{ch['instrument']}: {ch['prev'].get('bias')}/{ch['prev'].get('score')} → {ch['curr'].get('bias')}/{ch['curr'].get('score')}")
                    if diff["macro_changed"]:
                        st.caption("Makro: " + str(diff["macro_changed"]))
                    for line in diff["summary_text"]:
                        st.markdown(f"- {line}")
                else:
                    st.caption("Brak poprzedniego raportu do porównania.")

def run_report():
    """Uruchamia pelny raport i zwraca (wyniki, makro, payload)."""
    from main import generuj_raport
    import sys
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        out = generuj_raport(tryb="STANDARDOWY")
        if len(out) >= 3:
            return out[0], out[1], out[2]
        return out[0], out[1], {}
    finally:
        sys.stdout = old_stdout


def _save_report_to_archive(wyniki, makro, payload):
    """Zapisuje wygenerowany raport do archiwum (ta sama struktura co przy wysylce na Telegram)."""
    try:
        from report_archive import save_report
        teraz = datetime.now()
        instr = (payload or {}).get("instrukcja") or {}
        save_report(
            report_date=teraz.strftime("%Y-%m-%d"),
            report_time=teraz.strftime("%H:%M"),
            decision=instr.get("decision") or "WCHODZ Z OGRANICZENIAMI",
            summary={
                "health": "OK",
                "signals": [
                    {
                        "instrument": w.get("instrument"),
                        "bias": w.get("meta_bias"),
                        "score": w.get("lacznie"),
                        "conviction": w.get("conviction"),
                    }
                    for w in (wyniki or [])[:5]
                ],
                "macro": {
                    "DXY": makro.get("DXY", {}).get("value") if isinstance(makro.get("DXY"), dict) else None,
                    "US10Y": makro.get("US10Y", {}).get("value") if isinstance(makro.get("US10Y"), dict) else None,
                    "FED": makro.get("FEDFUNDS", {}).get("value") if isinstance(makro.get("FEDFUNDS"), dict) else None,
                    "OIL": makro.get("OIL_WTI", {}).get("value") if isinstance(makro.get("OIL_WTI"), dict) else None,
                },
                "reasons": instr.get("reasons", [])[:3],
                "ryzyka": instr.get("ryzyka", [])[:3],
            },
        )
    except Exception as e:
        # nie blokuj dashboardu
        pass


def _gate_dashboard():
    """Jeśli wlaczony wymog tokenu: pokaz formularz tokenu lub hasla admina. Zwraca True jesli dostep przyznany."""
    if not DASHBOARD_REQUIRE_TOKEN:
        st.session_state.dashboard_access = True
        return True
    if st.session_state.get("dashboard_access"):
        return True
    st.title("SofikaMax Agent – dostęp do platformy")
    st.caption("Wprowadź token dostępu (od administratora) lub hasło administratora.")
    token = st.text_input("Token dostępu", type="password", key="gate_token")
    pwd = st.text_input("Hasło administratora (opcjonalnie)", type="password", key="gate_pwd")
    if st.button("Wejdź"):
        if token and token.strip():
            try:
                from subscription_store import check_dashboard_token
                if check_dashboard_token(token.strip()):
                    st.session_state.dashboard_access = True
                    st.rerun()
                else:
                    st.error("Token nieprawidłowy lub wygasły.")
            except Exception as e:
                st.error(str(e))
        elif pwd and ADMIN_PASSWORD and pwd == ADMIN_PASSWORD:
            st.session_state.dashboard_access = True
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("Podaj prawidłowy token lub hasło administratora.")
    return False


def main():
    if DASHBOARD_REQUIRE_TOKEN and not st.session_state.get("dashboard_access"):
        _gate_dashboard()
        return

    if "report_data" not in st.session_state:
        st.session_state.report_data = None

    # Auto-zaladuj ostatni raport z harmonogramu (07:00, 12:30, 18:30, 20:30) – ten sam co na Telegram
    if st.session_state.report_data is None:
        try:
            from report_cache import load_report_cache
            cached = load_report_cache()
            if cached:
                st.session_state.report_data = cached
                st.session_state.report_from_schedule = True  # do wyswietlenia w sidebarze
        except Exception:
            pass

    # ---------- Sidebar (zawsze ten sam) ----------
    with st.sidebar:
        if DASHBOARD_REQUIRE_TOKEN:
            if st.button("Wyloguj (usun dostep)"):
                st.session_state.dashboard_access = False
                st.session_state.report_data = None
                st.rerun()
        st.markdown("**Raport analityczny**")
        if st.button("Odśwież raport (pobierz dane)", type="primary"):
            with st.spinner("Pobieram dane (1-2 min)..."):
                try:
                    wyniki, makro, payload = run_report()
                    st.session_state.report_data = (wyniki, makro, payload)
                    st.session_state.report_from_schedule = False
                    _save_report_to_archive(wyniki, makro, payload)
                    st.success("Raport załadowany i zapisany w archiwum.")
                except Exception as e:
                    st.error(f"Blad: {e}")
        if st.session_state.report_data is None:
            st.caption("Wygeneruj raport, aby zobaczyć COT, reżim, flow i instrukcję.")
        else:
            if st.session_state.get("report_from_schedule"):
                st.caption("Raport z harmonogramu (07:00 | 12:30 | 18:30 | 20:30). Przejdź do Przegląd / Desk.")
            else:
                st.caption("Raport załadowany. Przejdź do zakładki Przegląd / Desk.")
        st.divider()
        if ADMIN_PASSWORD:
            st.subheader("Admin")
            _render_subscription_admin()

    # ---------- Nagłówek desk (logo + tytuł) + pasek kursów (zawsze) ----------
    h1, h2 = st.columns([3, 1])
    with h1:
        logo_path = _logo_path()
        if logo_path:
            st.image(logo_path, width=180)
        else:
            st.markdown('<span class="desk-title">▣ SofikaMax Trading Desk</span>', unsafe_allow_html=True)
    with h2:
        st.markdown(f'<div style="text-align:right;"><span class="desk-clock">{datetime.now().strftime("%Y-%m-%d %H:%M")}</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="border-bottom:1px solid #2d3136;margin:0.5rem 0 1rem 0;"></div>', unsafe_allow_html=True)
    _render_ticker_bar()

    # ---------- Zakładki zawsze widoczne; przy braku raportu wyniki/payload puste, w zakładkach z raportem: komunikat ----------
    has_report = st.session_state.report_data is not None
    if has_report:
        wyniki, makro, payload = st.session_state.report_data
    else:
        wyniki, makro, payload = [], {}, {}
    pary_cross = payload.get("pary_cross", [])
    pary_usd = payload.get("pary_usd", [])
    flow_globalny = payload.get("flow_globalny") or {}
    rezimy = payload.get("rezimy", {})

    if has_report:
        ts = payload.get("timestamp", datetime.now().strftime("%d.%m.%Y %H:%M"))
        st.markdown(
            f'<p class="report-meta">Raport: {ts} | {len(wyniki)} instrumentów | COT + Reżim + Flow + Surprise + Sentiment + News</p>',
            unsafe_allow_html=True,
        )

    # Zakładki: Strona główna (platforma) | Kursy | Przegląd (raport) | ... | Archiwum | Źródła | Subskrypcje
    tab_names = ["🏠 Strona główna", "📈 Kursy & Wykresy", "📊 Przegląd", "🖥️ Desk", "📋 Siatka", "🔄 Cykle", "🌊 Przepływy", "⚡ Niespodzianka", "📈 Pary", "ℹ️ Info", "📁 Archiwum raportów", "📰 Źródła"]
    if ADMIN_PASSWORD:
        tab_names.append("🔐 Subskrypcje")
    tabs = st.tabs(tab_names)
    tab_home, tab_rates, tab_overview, tab_desk, tab_grid, tab_cycles, tab_flows, tab_surprise, tab_pary, tab_quality, tab_archive, tab_sources = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7], tabs[8], tabs[9], tabs[10], tabs[11]
    tab_subscriptions = tabs[12] if ADMIN_PASSWORD else None

    # --- Strona główna (ta sama platforma co bez raportu: historia, kwartal, tabele, wykresy, kalendarz, komunikaty) ---
    with tab_home:
        _render_home_platform()

    # --- Kursy & Wykresy ---
    with tab_rates:
        _render_rates_and_charts(key_prefix="tab_")

    # --- OVERVIEW ---
    with tab_overview:
        if not has_report:
            st.info("Kliknij **Odśwież raport (pobierz dane)** w panelu bocznym (☰), aby zobaczyć przegląd decyzji, metryk i COT.")
        else:
            # INSTRUKCJA (decyzja) – na górze, jak NIL
            instrukcja = payload.get("instrukcja") or {}
            decision = instrukcja.get("decision", "")
            if decision:
                if decision == "NIE WCHODŹ":
                    st.markdown('<div class="decision-box decision-no">🛑 DECYZJA: NIE WCHODŹ W NOWE POZYCJE</div>', unsafe_allow_html=True)
                elif decision == "WCHODŹ Z OGRANICZENIAMI":
                    st.markdown('<div class="decision-box decision-caution">⚠️ DECYZJA: WCHODŹ Z OGRANICZENIAMI (zmniejsz size, 1–2 setupy)</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="decision-box decision-go">✓ DECYZJA: MOŻESZ WCHODZIĆ (stosuj sugerowany size)</div>', unsafe_allow_html=True)
                for r in instrukcja.get("reasons", [])[:4]:
                    st.markdown(f"• {r}")
                if instrukcja.get("top_ideas"):
                    st.caption("**Jeśli wchodzisz:** " + " | ".join([f"{i.get('co','')} ({i.get('suggested_size_desc','')})" for i in instrukcja["top_ideas"][:3]]))

            st.markdown('<p class="section-title">Metryki</p>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div class="metric-card">**Instrumentów**<br><span style="font-size:1.8rem;color:#fafafa;">{len(wyniki)}</span></div>', unsafe_allow_html=True)
            with col2:
                flow_rezim = flow_globalny.get("rezim", "N/A")
                st.markdown(f'<div class="metric-card">**Reżim Flow**<br><span style="font-size:1.8rem;color:#fafafa;">{flow_rezim}</span></div>', unsafe_allow_html=True)
            with col3:
                usd_k = flow_globalny.get("usd_kierunek", "N/A")
                st.markdown(f'<div class="metric-card">**USD**<br><span style="font-size:1.8rem;color:#fafafa;">{usd_k}</span></div>', unsafe_allow_html=True)

            # Strategic Posture (makro, ryzyko, narracja, cykl, rotacja, governor)
            strat = payload.get("strategic") or {}
            g = strat.get("global") if isinstance(strat.get("global"), dict) else None
            if g:
                st.markdown('<p class="section-title">Strategic Posture</p>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="metric-card" style="padding:0.75rem;">'
                    f'<strong>Macro Mode:</strong> {g.get("macro_mode", "?")}<br>'
                    f'<strong>Risk Score:</strong> {g.get("risk_score", "?")}<br>'
                    f'<strong>Dominant Narrative:</strong> {g.get("dominant_narrative", "?")}<br>'
                    f'<strong>Cycle:</strong> {g.get("cycle_mode", "?")}<br>'
                    f'<strong>Rotation:</strong> {g.get("rotation_spec", "?")}<br>'
                    f'<strong>Deployment Governor:</strong> {g.get("deployment_governor", "?")}'
                    '</div>',
                    unsafe_allow_html=True,
                )

            claude_insight = payload.get("claude_insight")
            if claude_insight:
                st.markdown('<p class="section-title">Claude – analiza danych historycznych</p>', unsafe_allow_html=True)
                st.info(claude_insight)

            st.markdown('<p class="section-title">Pytaj Claude (własne pytanie o dane historyczne)</p>', unsafe_allow_html=True)
            with st.form("pytaj_claude"):
                custom_question = st.text_area("Twoje pytanie (np. ekstrema COT, ryzyko przed NFP, kierunek USD)", key="claude_question", height=80)
                submitted = st.form_submit_button("Wyślij do Claude")
            if submitted and custom_question and custom_question.strip():
                try:
                    from claude_analyzer import ask_claude
                    with st.spinner("Claude analizuje (archiwum + Twoje pytanie)..."):
                        result = ask_claude(custom_question.strip())
                    if result.get("ok") and result.get("summary"):
                        st.session_state["claude_custom_answer"] = result["summary"]
                        st.success("Odpowiedź Claude:")
                        st.markdown(result["summary"])
                    else:
                        st.error(result.get("error") or "Brak odpowiedzi.")
                except Exception as e:
                    st.error(str(e))
            if st.session_state.get("claude_custom_answer") and not (submitted and custom_question and custom_question.strip()):
                st.caption("Ostatnia odpowiedź (własne pytanie):")
                st.markdown(st.session_state["claude_custom_answer"])

            cot_insights = payload.get("cot_insights", [])
            if cot_insights:
                st.markdown('<p class="section-title">COT vs historia (ekstrema 1Y, dynamika 4 tyg)</p>', unsafe_allow_html=True)
                for ci in cot_insights[:8]:
                    ext = ci.get("extreme_type") or ""
                    badge = "badge-event" if ext else "badge-neut"
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<strong>{ci.get("instrument")}</strong> '
                        f'<span class="badge {badge}">{ext or "–"}</span> '
                        f'percentyl 1Y: {ci.get("percentile_1y") or "–"}% | trend 4 tyg: {ci.get("trend_4w") or "–"}<br>'
                        f'<span style="color:#9aa0a6;font-size:0.9rem;">{ci.get("cot_interpretation", "")}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            risk = payload.get("risk", {})
            if risk:
                st.markdown('<p class="section-title">Ryzyko i portfel</p>', unsafe_allow_html=True)
                st.info(risk.get("rekomendacja", ""))
                if risk.get("exposure"):
                    badges_html = []
                    for grupa, inst in risk["exposure"].items():
                        n = len(inst)
                        cls = "badge-mod" if n >= 2 else "badge-high"
                        badges_html.append(f'<span class="badge {cls}" style="margin-right:0.5rem;">{grupa}: {", ".join(inst)}</span>')
                    st.markdown("<div style='margin:0.5rem 0;'>" + " ".join(badges_html) + "</div>", unsafe_allow_html=True)
                for o in risk.get("ostrzezenia", []):
                    st.warning(o)

            commentary = payload.get("commentary", "")
            if commentary:
                st.markdown('<p class="section-title">Komentarz analityka</p>', unsafe_allow_html=True)
                st.markdown(commentary)

            workflow = payload.get("workflow", [])
            if workflow:
                st.markdown('<p class="section-title">Workflow – co i jak długo handlować</p>', unsafe_allow_html=True)
                for line in workflow[:6]:
                    with st.expander(f"{line.get('co', '')} | {line.get('jak_dlugo', '')}"):
                        st.write("**Sytuacja:**", line.get("sytuacja", ""))
                        st.write("**Wariant A:**", line.get("wariant_a", ""))
                        st.write("**Wariant B:**", line.get("wariant_b", ""))

            karta = payload.get("karta_doradcy", {})
            if karta:
                st.markdown('<p class="section-title">Karta doradcy</p>', unsafe_allow_html=True)
                st.info(karta.get("rekomendacja", ""))
                st.caption("Priorytet: " + ", ".join(karta.get("priorytet_instrumenty", [])))
                st.caption("Źródła: " + str(karta.get("zrodla", {})))
                st.caption("Trafność (historyczna): " + (karta.get("trafnosc_szac") or "–"))

            feedback = payload.get("feedback", {})
            if feedback.get("co_dziala") or feedback.get("co_nie_dziala"):
                st.markdown('<p class="section-title">Analiza feedbacku (co działa / nie działa)</p>', unsafe_allow_html=True)
                if feedback.get("co_dziala"):
                    st.success("Działa: " + "; ".join(feedback["co_dziala"]))
                if feedback.get("co_nie_dziala"):
                    st.warning("Nie działa: " + "; ".join(feedback["co_nie_dziala"]))
                if feedback.get("rekomendacja"):
                    st.info("Rekomendacja: " + " ".join(feedback["rekomendacja"]))

            conv_cal = payload.get("conviction_calibration", [])
            if conv_cal:
                st.caption("Kalibracja conviction: " + " | ".join([f"{r['conviction']}: {r['hit_rate_pct']}% (n={r['total']})" for r in conv_cal]))

            event_agg = payload.get("event_risk_aggregation", [])
            if event_agg:
                st.caption("Trafność wg event risk: " + " | ".join([f"{r['event_risk_level']}: {r['hit_rate_pct']}%" for r in event_agg]))

            user_fb = payload.get("user_feedback", [])
            if user_fb:
                st.caption("Twoje oceny: " + ", ".join([f"{r['para']} {r['useful_pct']}% pozytywnych" for r in user_fb[:5]]))

            st.markdown('<p class="section-title">Oceń sygnał (feedback użytkownika)</p>', unsafe_allow_html=True)
            try:
                from outcome_tracker import save_user_feedback
                report_date = datetime.now().strftime("%Y-%m-%d")
                pary = [p.get("para", "") for p in payload.get("pary_usd", [])[:8] if p.get("para")]
                if not pary:
                    pary = ["EUR/USD", "GBP/USD", "AUD/USD", "XAU/USD"]
                para_sel = st.selectbox("Para", pary, key="fb_para")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Przydatny"):
                        save_user_feedback(report_date, para_sel, True)
                        st.success("Zapisano: przydatny.")
                with col2:
                    if st.button("Nie przydatny"):
                        save_user_feedback(report_date, para_sel, False)
                        st.info("Zapisano: nie przydatny.")
            except Exception as e:
                st.caption("Feedback: " + str(e))

            verified = payload.get("verified", [])
            if verified:
                hit = sum(1 for v in verified if v.get("hit"))
                st.caption(f"Weryfikacja sygnalow: {hit}/{len(verified)} trafionych (horyzont ~2 tyg).")

            st.markdown('<p class="section-title">Scoring per waluta</p>', unsafe_allow_html=True)
            df_overview = pd.DataFrame([{
                "WALUTA": w["instrument"],
                "BIAS": w["bias"],
                "SCORE": w["lacznie"],
                "CONVICTION": w["conviction"],
                "SYTUACJA": w.get("situation_label", w.get("meta_type", "")),
                "REZIM": w.get("typ_rezimu", ""),
                "FLOW": w.get("flow_score", 0),
                "HORIZON": w.get("meta_horizon", ""),
            } for w in wyniki])
            st.dataframe(df_overview, use_container_width=True, hide_index=True)

    # --- DESK – pozycje, sugestie, wykonanie (paper) ---
    with tab_desk:
        st.subheader("Desk – pozycje i zlecenia")
        try:
            from position_tracker import get_positions_summary
            from config import DESK_MODE
        except ImportError:
            get_positions_summary = None
            DESK_MODE = "paper"
        summary = get_positions_summary() if get_positions_summary else {"count": 0, "symbols": [], "positions": []}
        open_pos = summary.get("positions", [])
        st.markdown(f'<p class="section-title">Otwarte pozycje ({len(open_pos)})</p>', unsafe_allow_html=True)
        if open_pos:
            df_pos = pd.DataFrame([{"SYMBOL": p.get("symbol"), "SIDE": p.get("side"), "ENTRY": p.get("entry_time"), "SOURCE": p.get("source", "")} for p in open_pos])
            st.dataframe(df_pos, use_container_width=True, hide_index=True)
        else:
            st.info("Brak otwartych pozycji (paper/live).")

        desk = payload.get("desk") or {}
        suggested = desk.get("suggested_orders", [])
        st.markdown(f'<p class="section-title">Sugerowane zlecenia ({len(suggested)})</p>', unsafe_allow_html=True)
        if suggested:
            for o in suggested:
                badge = "badge-long" if (o.get("side") or "").upper() == "LONG" else "badge-short"
                st.markdown(
                    f'<div class="metric-card">'
                    f'<span class="badge {badge}">{o.get("side")}</span> <strong>{o.get("symbol")}</strong> '
                    f'{o.get("size_pct")}% &nbsp; <span style="color:#9aa0a6;">{o.get("rationale", "")[:80]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if DESK_MODE == "paper":
                if st.button("Wykonaj sugerowane (paper)"):
                    try:
                        from desk_controller import run_desk_cycle
                        inst = payload.get("instrukcja", {})
                        risk_p = payload.get("risk", {})
                        res = run_desk_cycle(instruction=inst, risk=risk_p, execute=True, max_orders=3)
                        ex = res.get("executed", [])
                        st.success(f"Wykonano (paper): {len(ex)} zleceń. Odśwież raport, aby zobaczyć pozycje.")
                        st.session_state.desk_last_executed = ex
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("desk_last_executed"):
                st.caption("Ostatnie wykonanie (paper): " + ", ".join([f"{e.get('symbol')} {e.get('side')}" for e in st.session_state.desk_last_executed]))
        else:
            st.caption("Brak sugerowanych zleceń (decyzja NIE WCHODŹ lub brak wolnych slotów).")
        executed = desk.get("executed", [])
        if executed:
            st.caption("W tym raporcie wykonano (paper): " + ", ".join([f"{e.get('symbol')} {e.get('side')}" for e in executed]))

    # --- NARRATIVE GRID – Phase + Score bar jak NIL ---
    with tab_grid:
        st.subheader("Narrative Grid")
        st.caption("Phase + Clock + Score. Wyższy score = silniejsza narracja.")
        phase_color = {"EXPANSION": "#0f9d58", "RECOVERY": "#0f9d58", "SLOWDOWN": "#f9ab00", "CONTRACTION": "#ea4335"}
        for w in wyniki[:9]:
            phase = (w.get("faza") or "N/A").upper()
            color = phase_color.get(phase, "#9aa0a6")
            score = w.get("lacznie", 0)
            pct = min(100, max(0, score))
            conv = w.get("conviction", "")
            badge = "badge-high" if conv == "WYSOKI" else ("badge-mod" if conv == "UMIARKOWANY" else "badge-low")
            st.markdown(
                f'<div class="metric-card">'
                f'<strong>{w["instrument"]}</strong> &nbsp; <span style="color:{color};font-weight:600;">{w.get("faza") or "N/A"}</span> &nbsp; {w.get("zegar", "N/A")}<br>'
                f'<span class="badge {badge}">{conv}</span> &nbsp; Score {score}/100 &nbsp; '
                f'<div class="progress-wrap"><div class="progress-fill" style="width:{pct}%;background:{color};"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        df_grid = pd.DataFrame([{
            "WALUTA": w["instrument"],
            "PHASE": w.get("faza", ""),
            "CLOCK": w.get("zegar", ""),
            "SCORE": w["lacznie"],
            "CONVICTION": w["conviction"],
            "META_BIAS": w.get("meta_bias", ""),
            "META_TYPE": w.get("meta_type", ""),
            "HORIZON": w.get("meta_horizon", ""),
        } for w in wyniki])
        st.dataframe(df_grid, use_container_width=True, hide_index=True)

    # --- CYCLES (M1) – karty jak NIL ---
    with tab_cycles:
        st.subheader("M1: Cycle Intelligence")
        st.caption("Faza cyklu ekonomicznego (CLI) + zegar (GOLDILOCKS / REFLATION / DEFLATION / STAGFLATION).")
        phase_to_class = {"EXPANSION": "expansion", "RECOVERY": "expansion", "SLOWDOWN": "slowdown", "CONTRACTION": "contraction"}
        for i in range(0, len(wyniki), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(wyniki):
                    break
                w = wyniki[idx]
                cykl = w.get("cykl_obj") or {}
                phase = (cykl.get("phase") or "N/A").upper()
                card_class = phase_to_class.get(phase, "") if phase != "N/A" else ""
                cli = cykl.get("cli") or 0
                clock = cykl.get("clock", "N/A")
                slope = cykl.get("cli_slope") or 0
                with col:
                    st.markdown(
                        f'<div class="cycle-card {card_class}">'
                        f'<strong>{w["instrument"]}</strong> &nbsp; <span style="color:#9aa0a6;font-size:0.85rem;">{phase}</span><br>'
                        f'<span style="font-size:0.9rem;">{clock}</span> &nbsp; CLI {cli:.1f} ({slope:+.2f})<br>'
                        f'<span style="font-size:1.25rem;color:#fafafa;">{w["lacznie"]}</span> score'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        st.markdown('<p class="section-title">Tabela cykli</p>', unsafe_allow_html=True)
        cycles_data = []
        for w in wyniki:
            cykl = w.get("cykl_obj") or {}
            cycles_data.append({
                "WALUTA": w["instrument"],
                "PHASE": cykl.get("phase", "N/A"),
                "CLOCK": cykl.get("clock", "N/A"),
                "CLI": cykl.get("cli", 0),
                "CLI_SLOPE": cykl.get("cli_slope", 0),
                "MOMENTUM": cykl.get("cli_momentum", "N/A"),
                "MATURITY": cykl.get("maturity", "N/A"),
            })
        st.dataframe(pd.DataFrame(cycles_data), use_container_width=True, hide_index=True)

    # --- FLOWS (M2) – paski jak NIL ---
    with tab_flows:
        st.subheader("M2: Cross-Asset Flow")
        st.caption("Reżim RISK-ON/OFF, USD, surowce. Flow score per waluta (0–20).")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div class="metric-card">**Reżim** {flow_globalny.get("rezim", "N/A")} (siła {flow_globalny.get("rezim_sila", 0)}/4)<br>**USD** {flow_globalny.get("usd_kierunek", "N/A")} | **Surowce** {flow_globalny.get("surowce_kierunek", "N/A")}</div>', unsafe_allow_html=True)
        with col2:
            cr = flow_globalny.get("crypto", {})
            if cr and cr.get("btc_cena", 0) > 0:
                st.markdown(f'<div class="metric-card">**BTC** ${cr.get("btc_cena", 0):,.0f} | {cr.get("btc_trend", "?")} | 20d: {cr.get("btc_zmiana_20d", 0):+.1f}%</div>', unsafe_allow_html=True)
        waluty_flow = flow_globalny.get("waluty", {})
        if waluty_flow:
            st.markdown('<p class="section-title">Flow score (0–20) per waluta</p>', unsafe_allow_html=True)
            for k, v in list(waluty_flow.items())[:12]:
                sc = v.get("score", 0)
                pct = min(100, max(0, (sc / 20) * 100))
                color = "#0f9d58" if sc >= 12 else ("#f9ab00" if sc >= 8 else "#ea4335")
                div = f'<div style="margin:0.4rem 0;"><strong>{k}</strong> {sc}/20 &nbsp; <div class="progress-wrap"><div class="progress-fill" style="width:{pct}%;background:{color};"></div></div></div>'
                st.markdown(div, unsafe_allow_html=True)
            flow_rows = [{"WALUTA": k, "SCORE": v.get("score", 0), "DYWERGENCJA": "Tak" if v.get("dywergencja") else "Nie"} for k, v in waluty_flow.items()]
            st.dataframe(pd.DataFrame(flow_rows), use_container_width=True, hide_index=True)

    # --- SURPRISE (M3) – kolorowane wartości jak NIL ---
    with tab_surprise:
        st.subheader("M3: Surprise Intelligence")
        st.caption("Zaskoczenia makro (Surprise 4W) + momentum. Źródło: surprise_engine.")
        for w in wyniki[:9]:
            surp = w.get("surprise_4w") or 0
            event = w.get("event_risk", "N/A")
            color = "#0f9d58" if surp > 0 else ("#ea4335" if surp < 0 else "#9aa0a6")
            badge_ev = "badge-event" if event in ("WYSOKI", "KRYTYCZNY") else "badge-neut"
            st.markdown(
                f'<div class="metric-card" style="border-left-color:{color};">'
                f'<strong>{w["instrument"]}</strong> &nbsp; '
                f'<span style="color:{color};font-weight:600;">Surprise 4W: {surp:+.1f}</span> &nbsp; '
                f'<span class="badge {badge_ev}">{event}</span> &nbsp; {w.get("news_bias", "N/A")}'
                f'</div>',
                unsafe_allow_html=True,
            )
        surprise_rows = []
        for w in wyniki:
            surprise_rows.append({
                "WALUTA": w["instrument"],
                "SURPRISE_4W": w.get("surprise_4w", 0),
                "NEWS_BIAS": w.get("news_bias", "N/A"),
                "EVENT_RISK": w.get("event_risk", "N/A"),
            })
        st.dataframe(pd.DataFrame(surprise_rows), use_container_width=True, hide_index=True)

    # --- PARY / DASHBOARD – badge LONG/SHORT jak NIL ---
    with tab_pary:
        st.subheader("Dashboard – co i jak długo handlować")
        st.caption("Pary do handlu: BIAS (LONG/SHORT), TYP sygnału, HORIZON.")

        dashboard_rows = []
        for w in wyniki:
            bias_label = w.get("meta_bias", "CZEKAJ")
            if bias_label == "BUY":
                bias_txt, badge_bias = "LONG", "badge-long"
                typ = w.get("meta_type", "TREND")
            elif bias_label == "SELL":
                bias_txt, badge_bias = "SHORT", "badge-short"
                typ = w.get("meta_type", "TREND")
            else:
                bias_txt, badge_bias = "NEUT", "badge-neut"
                typ = "NO TRADE"
            horizon = w.get("meta_horizon", "-") if bias_label != "CZEKAJ" else "-"
            conv = w.get("conviction", "")
            badge_conv = "badge-high" if conv == "WYSOKI" else ("badge-mod" if conv == "UMIARKOWANY" else "badge-low")
            dashboard_rows.append({
                "INSTRUMENT": w["instrument"],
                "BIAS": bias_txt,
                "BADGE_BIAS": badge_bias,
                "TYPE": typ,
                "HORIZON": horizon,
                "SCORE": w["lacznie"],
                "CONVICTION": conv,
                "BADGE_CONV": badge_conv,
            })
        # Karty w stylu NIL (PAIR | BIAS badge | TYPE | HORIZON)
        for r in dashboard_rows[:9]:
            st.markdown(
                f'<div class="metric-card">'
                f'<strong>{r["INSTRUMENT"]}</strong> &nbsp; '
                f'<span class="badge {r["BADGE_BIAS"]}">{r["BIAS"]}</span> &nbsp; '
                f'<span class="badge {r["BADGE_CONV"]}">{r["CONVICTION"] or "–"}</span> &nbsp; '
                f'{r["TYPE"]} &nbsp; <span style="color:#9aa0a6;">{r["HORIZON"]}</span> &nbsp; score {r["SCORE"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.dataframe(pd.DataFrame([{k: r[k] for k in ["INSTRUMENT", "BIAS", "TYPE", "HORIZON", "SCORE"]} for r in dashboard_rows]), use_container_width=True, hide_index=True)

        st.subheader("Pary cross (waluta vs waluta)")
        if pary_cross:
            df_cross = pd.DataFrame([{"PARA": p["para"], "SILA": p["sila_sygnalu"], "CONVICTION": p["conviction"], "TYP": p["typ_sygnalu"], "RYZYKO": p["ryzyko"]} for p in pary_cross[:12]])
            st.dataframe(df_cross, use_container_width=True, hide_index=True)
        else:
            st.info("Brak wyraznych sygnalow cross.")

        st.subheader("Pary vs USD")
        if pary_usd:
            df_usd = pd.DataFrame([{"PARA": p["para"], "KIERUNEK": p["kierunek"], "SILA": p["sila_sygnalu"], "CONVICTION": p["conviction"], "TYP": p["typ_sygnalu"], "LUSTRZANE": "Tak" if p.get("lustrzane_potwierdzenie") else "Nie"} for p in pary_usd[:12]])
            st.dataframe(df_usd, use_container_width=True, hide_index=True)
        else:
            st.info("Brak sygnalow vs USD.")

    # --- DATA QUALITY / INFO ---
    with tab_quality:
        st.subheader("Raporty Telegram (SofikaMax Agent)")
        st.markdown("""
        **Co wysylamy na Telegram (automatycznie 4 razy dziennie):**

        1. **Wiadomosc glowna** (podsumowanie):
           - SYSTEM HEALTH (ALL_GREEN / WARNING)
           - Dataset: liczba instrumentow, zrodla 6/6 warstw
           - Aktywne sygnaly (BUY/SELL, score, type, horyzont, faza)
           - Makro (DXY, US10Y, krzywa, FED, ropa)
           - Nastepne raporty: 07:00 | 12:30 | 18:30 | 20:30

        2. **Zalacznik** \`daily_report_YYYYMMDD_HHMM.md\`:
           - Pelny raport w Markdown (tabela scoringu, makro)
           - Do archiwum lub otwarcia w edytorze

        **Harmonogram:** 07:00 (poranny) | 12:30 (poludniowy) | 18:30 (wieczorny) | 20:30 (nocny)
        """)
        st.subheader("Data Quality & Zrodla")
        st.markdown("""
        - **COT:** CFTC (Commitment of Traders) - dane instytucjonalne  
        - **Regime:** yfinance Weekly, 40EMA + HH/HL + ATR  
        - **Flow:** yfinance ETF (GLD, TLT, SPY, UUP, USO, EEM, FXE, FXB, FXY) + BTC-USD  
        - **Surprise:** FRED (zaskoczenia makro per waluta)  
        - **Sentiment:** MyFXBook (retail, kontrarianski) - opcjonalnie  
        - **News:** NewsAPI  
        - **Events:** ForexFactory / reczny kalendarz  
        """)
        st.caption("COT is contextual, not predictive. SofikaMax Agent nie jest doradca inwestycyjnym.")

    # --- Archiwum raportów (zapisy z Telegram/PDF) + wykresy + porównanie ---
    with tab_archive:
        _render_report_archive()

    # --- Źródła: preferowane media, komunikaty oficjalne ---
    with tab_sources:
        st.subheader("Źródła informacji")
        st.markdown('<p class="section-title">Preferowane źródła wiadomości (Reuters, AP, BBC, Guardian, NYT, WSJ…)</p>', unsafe_allow_html=True)
        try:
            from config import NEWS_PREFERRED_SOURCES
            st.caption(", ".join(NEWS_PREFERRED_SOURCES) if NEWS_PREFERRED_SOURCES else "Brak listy w config.")
        except Exception:
            st.caption("Reuters, Associated Press, BBC News, The Guardian, The New York Times, Wall Street Journal, The Economist.")
        st.markdown('<p class="section-title">Komunikaty oficjalne (banki centralne, wybrane instytucje)</p>', unsafe_allow_html=True)
        headlines = _get_latest_official_headlines(limit=25)
        if headlines:
            for h in headlines:
                st.markdown(f"**{h.get('source', '')}** ({h.get('region', '')}) · [{h.get('title', '')[:80]}]({h.get('link', '#') or '#'})")
            if st.button("Pobierz najnowsze komunikaty (RSS)", key="fetch_official_tab"):
                try:
                    from official_sources import fetch_and_store
                    n = fetch_and_store()
                    st.success(f"Zapisano {n} komunikatów.")
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        else:
            st.caption("Brak zapisanych komunikatów. Źródła: ECB, Federal Reserve, BOE, NBP (RSS). Filtrowanie: stopy, sankcje, handel, ropa.")
            if st.button("Pobierz komunikaty oficjalne", key="fetch_official_tab_first"):
                try:
                    from official_sources import fetch_and_store
                    n = fetch_and_store()
                    st.success(f"Pobrano i zapisano {n} komunikatów.")
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        st.markdown('<p class="section-title">Dokumentacja</p>', unsafe_allow_html=True)
        st.caption("Więcej: docs/ZRODLA_INFORMACJI.md – agencje, API, źródła rządowe G20.")

    if tab_subscriptions is not None:
        with tab_subscriptions:
            _render_subscription_admin()


if __name__ == "__main__":
    main()
