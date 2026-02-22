# =============================================================================
# report_pdf.py - Raport PDF: poziom instytucjonalny, język polski, ciągłość z poprzednim
# KUPNO / SPRZEDAZ / CZEKAJ / RYZYKO – czytelny jak dla amatora, wygląd nowoczesny (ciemny).
# =============================================================================

import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_SCRIPT_DIR, "assets", "sofikamax_logo.png")

# Czcionki z obsługą polskich znaków (ł, ó, ę, ż, ą, ś, ć, ź, ń) – bez tego PDF pokazuje kwadraciki
PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _registered = False
    _win = os.environ.get("WINDIR", "C:\\Windows")
    _arial = os.path.join(_win, "Fonts", "arial.ttf")
    _arialbd = os.path.join(_win, "Fonts", "arialbd.ttf")
    if os.path.isfile(_arial):
        pdfmetrics.registerFont(TTFont("ArialPL", _arial))
        PDF_FONT = "ArialPL"
        _registered = True
    if os.path.isfile(_arialbd):
        pdfmetrics.registerFont(TTFont("ArialPL-Bold", _arialbd))
        PDF_FONT_BOLD = "ArialPL-Bold"
    if not _registered:
        for _path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ):
            if os.path.isfile(_path):
                pdfmetrics.registerFont(TTFont("ArialPL", _path))
                PDF_FONT = "ArialPL"
                _path_bold = _path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf")
                if os.path.isfile(_path_bold):
                    pdfmetrics.registerFont(TTFont("ArialPL-Bold", _path_bold))
                    PDF_FONT_BOLD = "ArialPL-Bold"
                break
except Exception:
    pass

A4_W, A4_H = 595.28, 841.89
MARGIN = 52
LINE = 13
SMALL = 9
NORMAL = 10
HEAD = 12
TITLE = 16

# Kolory – ciemny motyw "z kosmosu"
RGB_BG = (0.04, 0.06, 0.10)
RGB_TEXT = (0.95, 0.96, 0.98)
RGB_ACCENT = (0.35, 0.75, 0.95)
RGB_MUTED = (0.65, 0.70, 0.78)
RGB_CARD = (0.08, 0.11, 0.16)


def _wrap(s: str, max_chars: int = 78) -> List[str]:
    """Dzieli tekst na linie (słowa, max znaków)."""
    if not s or max_chars <= 0:
        return []
    out = []
    for para in s.replace("\r", "").split("\n"):
        words = para.split()
        line = ""
        for w in words:
            if line and len(line) + 1 + len(w) > max_chars:
                out.append(line)
                line = w
            else:
                line = (line + " " + w) if line else w
        if line:
            out.append(line)
    return out


def _new_page_needed(y: float, need: float = 80) -> bool:
    return y < (MARGIN + need)


def _draw_pdf(
    wyniki: List[Dict],
    makro: Dict,
    payload: Dict,
    buffer: BytesIO,
    logo_path: Optional[str] = None,
    include_charts: bool = True,
) -> None:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise ImportError("Zainstaluj reportlab: pip install reportlab")

    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4_W, A4_H
    margin = MARGIN
    y = h - margin

    def set_dark_page():
        c.setFillColorRGB(*RGB_BG)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColorRGB(*RGB_TEXT)
        c.setFont(PDF_FONT, NORMAL)

    def draw_line(text: str, font: str = None, size: int = NORMAL, indent: float = 0, max_len: int = 78):
        if font is None:
            font = PDF_FONT
        nonlocal y
        for frag in _wrap(text, max_len):
            c.setFont(font, size)
            c.setFillColorRGB(*RGB_TEXT)
            c.drawString(margin + indent, y, frag[:95])
            y -= LINE
        return

    def draw_line_one(text: str, font: str = None, size: int = NORMAL, indent: float = 0):
        if font is None:
            font = PDF_FONT
        nonlocal y
        c.setFont(font, size)
        c.setFillColorRGB(*RGB_TEXT)
        c.drawString(margin + indent, y, (text[:95] + "..") if len(text) > 95 else text)
        y -= LINE

    def space(pts: float = LINE):
        nonlocal y
        y -= pts

    def page_break():
        nonlocal y
        c.showPage()
        set_dark_page()
        y = h - margin

    set_dark_page()

    # ---------- Okładka ----------
    logo = logo_path or (LOGO_PATH if os.path.isfile(LOGO_PATH) else None)
    if logo and os.path.isfile(logo):
        try:
            c.drawImage(logo, margin, y - 20 * mm, width=36 * mm, preserveAspectRatio=True)
            y -= 24 * mm
        except Exception:
            pass

    c.setFillColorRGB(*RGB_ACCENT)
    c.setFont(PDF_FONT_BOLD, TITLE)
    c.drawString(margin, y, "Raport analityczny")
    y -= LINE * 1.3
    c.setFillColorRGB(*RGB_TEXT)
    c.setFont(PDF_FONT, NORMAL)
    teraz = datetime.now().strftime("%d.%m.%Y  %H:%M")
    godzina = datetime.now().hour
    if godzina < 10:
        pora = "Raport poranny"
    elif godzina < 15:
        pora = "Raport południowy"
    elif godzina < 20:
        pora = "Raport wieczorny"
    else:
        pora = "Raport nocny"
    c.drawString(margin, y, f"{pora}  |  {teraz}")
    y -= LINE * 1.5

    instr = (payload or {}).get("instrukcja") or {}
    decision = instr.get("decision") or "WCHODŹ Z OGRANICZENIAMI"

    # Wniosek po polsku: KUPNO / CZEKAJ / ostrożne wejście
    if "NIE WCHODŹ" in decision.upper():
        wniosek = "CZEKAJ – nie wchodź w nowe pozycje"
        podpis = "Ocena: ryzyko lub jakość setupów nie uzasadnia nowej ekspozycji."
    elif "OGRANICZENIAMI" in decision.upper():
        wniosek = "Ostrożne wejście – ogranicz wielkość, maksymalnie 1–2 setupy"
        podpis = "Ocena: warunki pozwalają tylko na ostrożną, ograniczoną ekspozycję."
    else:
        wniosek = "Można wchodzić – stosuj sugerowaną wielkość i limity korelacji"
        podpis = "Ocena: setupy spełniają kryteria siły rekomendacji i ryzyka."

    c.setFillColorRGB(*RGB_ACCENT)
    c.setFont(PDF_FONT_BOLD, HEAD)
    c.drawString(margin, y, "Wniosek inwestycyjny")
    y -= LINE
    c.setFillColorRGB(*RGB_TEXT)
    c.setFont(PDF_FONT, NORMAL)
    draw_line(wniosek, PDF_FONT, NORMAL, max_len=75)
    c.setFillColorRGB(*RGB_MUTED)
    c.setFont(PDF_FONT, SMALL)
    draw_line(podpis, PDF_FONT, SMALL, max_len=78)
    c.setFillColorRGB(*RGB_TEXT)
    y -= 2
    c.setFont(PDF_FONT_BOLD, SMALL)
    c.drawString(margin, y, "Uzasadnienie")
    y -= LINE
    c.setFont(PDF_FONT, SMALL)
    for r in instr.get("reasons", [])[:4]:
        draw_line("• " + r, PDF_FONT, SMALL, indent=4, max_len=74)
    space(6)

    # ---------- Strategic Posture (makro, ryzyko, narracja, cykl, rotacja, governor) ----------
    strat = (payload or {}).get("strategic") or {}
    g = strat.get("global") if isinstance(strat.get("global"), dict) else None
    if g:
        if _new_page_needed(y, 120):
            page_break()
        c.setFillColorRGB(*RGB_ACCENT)
        c.setFont(PDF_FONT_BOLD, HEAD)
        c.drawString(margin, y, "Strategic Posture")
        y -= LINE
        c.setFillColorRGB(*RGB_MUTED)
        c.setFont(PDF_FONT, SMALL)
        for key, label in [
            ("macro_mode", "Macro Mode"),
            ("risk_score", "Risk Score"),
            ("dominant_narrative", "Dominant Narrative"),
            ("cycle_mode", "Cycle"),
            ("rotation_spec", "Rotation"),
            ("deployment_governor", "Deployment Governor"),
        ]:
            val = (g.get(key) or "?").strip()
            if len(val) > 75:
                val = val[:72] + "..."
            c.setFillColorRGB(*RGB_MUTED)
            c.drawString(margin, y, label + ":")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            for frag in _wrap(val, 70):
                c.drawString(margin + 4, y, frag[:95])
                y -= LINE
            y -= 2
        c.setFillColorRGB(*RGB_TEXT)
        space(4)

    # ---------- Ciągłość z poprzednim raportem ----------
    continuity = None
    try:
        from continuity_narrative import get_previous_report, build_continuity_narrative
        prev = get_previous_report()
        continuity = build_continuity_narrative(
            current_decision=decision,
            current_reasons=instr.get("reasons", []),
            wyniki=wyniki,
            makro=makro,
            payload=payload,
            previous_report=prev,
        )
    except Exception:
        pass

    if continuity and (continuity.get("paragrafy") or continuity.get("cot_sentyment") or continuity.get("analiza_kwartalna")):
        if _new_page_needed(y, 180):
            page_break()
        c.setFillColorRGB(*RGB_ACCENT)
        c.setFont(PDF_FONT_BOLD, HEAD)
        c.drawString(margin, y, "Co się zmieniło i dlaczego – ciągłość z poprzednim raportem")
        y -= LINE * 1.2
        c.setFillColorRGB(*RGB_TEXT)
        c.setFont(PDF_FONT, SMALL)
        if continuity.get("analiza_kwartalna"):
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "Analiza kwartalna (ostatnie raporty pod kontrolą)")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            for frag in _wrap(continuity["analiza_kwartalna"], 76):
                c.drawString(margin, y, frag[:95])
                y -= LINE
            space(2)
        for p in continuity.get("paragrafy", []):
            draw_line(p, PDF_FONT, SMALL, max_len=76)
            y -= 1
        if continuity.get("cot_sentyment"):
            space(2)
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "COT i sentyment (zawsze razem)")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            draw_line(continuity["cot_sentyment"], PDF_FONT, SMALL, max_len=76)
        if continuity.get("stopy_dolar"):
            space(2)
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "Stopy procentowe i dolar")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            draw_line(continuity["stopy_dolar"], PDF_FONT, SMALL, max_len=76)
        if continuity.get("euro_frank_makro"):
            draw_line(continuity["euro_frank_makro"], PDF_FONT, SMALL, max_len=76)
        if continuity.get("kalendarz"):
            space(2)
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "Kalendarz wydarzeń")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            draw_line(continuity["kalendarz"], PDF_FONT, SMALL, max_len=76)
        if continuity.get("komunikaty_oficjalne"):
            space(2)
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "Komunikaty oficjalne (banki centralne)")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            draw_line(continuity["komunikaty_oficjalne"], PDF_FONT, SMALL, max_len=76)
        if continuity.get("co_wzielismy"):
            space(2)
            c.setFillColorRGB(*RGB_MUTED)
            c.setFont(PDF_FONT_BOLD, SMALL)
            c.drawString(margin, y, "Co wzięliśmy pod uwagę")
            y -= LINE
            c.setFillColorRGB(*RGB_TEXT)
            for frag in _wrap(continuity["co_wzielismy"], 76):
                c.drawString(margin, y, frag[:95])
                y -= LINE
        space(6)

    if _new_page_needed(y, 140):
        page_break()

    # ---------- Rekomendacje handlowe (KUPNO / SPRZEDAZ) ----------
    c.setFillColorRGB(*RGB_ACCENT)
    c.setFont(PDF_FONT_BOLD, HEAD)
    c.drawString(margin, y, "1. Rekomendacje handlowe – co warto handlować")
    y -= LINE * 1.2
    c.setFillColorRGB(*RGB_TEXT)

    workflow = (payload or {}).get("workflow") or []
    top_workflow = [line for line in workflow if line.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:6]
    conv_pl = {"WYSOKI": "wysoka", "UMIARKOWANY": "umiarkowana"}

    if not top_workflow:
        c.setFont(PDF_FONT, NORMAL)
        draw_line("Brak setupów spełniających próg siły rekomendacji. Nie wymuszaj transakcji – CZEKAJ.", PDF_FONT, NORMAL, max_len=76)
        y -= LINE
    else:
        c.setFont(PDF_FONT, SMALL)
        for i, line in enumerate(top_workflow[:5], 1):
            if _new_page_needed(y, 55):
                page_break()
                c.setFillColorRGB(*RGB_TEXT)
            co = line.get("co", "")
            # Long/Short -> KUPNO/SPRZEDAZ
            if "Long" in co or "KUPNO" in co.upper():
                co_pl = co.replace("Long", "KUPNO").replace("LONG", "KUPNO")
            elif "Short" in co or "SPRZEDAZ" in co.upper():
                co_pl = co.replace("Short", "SPRZEDAZ").replace("SHORT", "SPRZEDAZ")
            else:
                co_pl = co
            c.setFont(PDF_FONT_BOLD, SMALL)
            draw_line_one(f"{i}. {co_pl}", PDF_FONT_BOLD, SMALL)
            c.setFont(PDF_FONT, SMALL)
            conv = line.get("conviction", "")
            conv_txt = conv_pl.get(conv, conv)
            horizon = line.get("jak_dlugo", "")
            size_desc = line.get("suggested_size_desc", "")
            draw_line_one(f"   Siła rekomendacji: {conv_txt}  |  Horyzont: {horizon}  |  Wielkość: {size_desc}", PDF_FONT, SMALL, indent=4)
            rationale = (line.get("rationale") or "")
            if rationale:
                draw_line("   " + rationale, PDF_FONT, SMALL, indent=4, max_len=72)
            y -= 2

    space(5)

    # ---------- Wykresy ----------
    chart_images: List[Tuple[str, bytes]] = []
    if include_charts and top_workflow:
        try:
            from report_charts import render_charts_for_workflow
            chart_images = render_charts_for_workflow(top_workflow, max_charts=4, days=30)
        except Exception:
            pass

    img_w = (w - 2 * margin - 10) / 2
    img_h = 52
    for idx, (pair_name, png_bytes) in enumerate(chart_images):
        if _new_page_needed(y, img_h + 35):
            page_break()
            c.setFillColorRGB(*RGB_TEXT)
        try:
            img = ImageReader(BytesIO(png_bytes))
            col = idx % 2
            x_img = margin + col * (img_w + 10)
            y_img = y - img_h
            c.drawImage(img, x_img, y_img, width=img_w, height=img_h)
            c.setFont(PDF_FONT, 8)
            c.setFillColorRGB(*RGB_MUTED)
            c.drawString(x_img, y_img - 10, pair_name)
            c.setFillColorRGB(*RGB_TEXT)
            if col == 1:
                y -= img_h + 16
        except Exception:
            pass
    if chart_images and len(chart_images) % 2 == 1:
        y -= img_h + 16
    space(5)

    # ---------- Czego unikać i RYZYKO ----------
    if _new_page_needed(y, 160):
        page_break()
        c.setFillColorRGB(*RGB_TEXT)

    c.setFillColorRGB(*RGB_ACCENT)
    c.setFont(PDF_FONT_BOLD, HEAD)
    c.drawString(margin, y, "2. Czego unikać i co wymaga potwierdzenia (RYZYKO)")
    y -= LINE * 1.2
    c.setFillColorRGB(*RGB_TEXT)
    c.setFont(PDF_FONT, SMALL)
    ryzyka = instr.get("ryzyka", [])
    if ryzyka:
        for r in ryzyka[:5]:
            draw_line("• " + r, PDF_FONT, SMALL, indent=4, max_len=74)
    else:
        draw_line("Stosuj się do wniosku inwestycyjnego i sugerowanej wielkości; nie koncentruj ekspozycji w jednej grupie korelacyjnej.", PDF_FONT, SMALL, max_len=76)
    space(2)
    c.setFillColorRGB(*RGB_MUTED)
    c.setFont(PDF_FONT_BOLD, SMALL)
    c.drawString(margin, y, "Co potwierdza lub unieważnia naszą ocenę")
    y -= LINE
    c.setFillColorRGB(*RGB_TEXT)
    first_idea = top_workflow[0] if top_workflow else {}
    va = (first_idea.get("wariant_a") or "")[:80]
    vb = (first_idea.get("wariant_b") or "")[:80]
    if va or vb:
        if va:
            draw_line("Potwierdzenie: " + va, PDF_FONT, SMALL, indent=4, max_len=72)
        if vb:
            draw_line("Unieważnienie: " + vb, PDF_FONT, SMALL, indent=4, max_len=72)
    else:
        draw_line("Obserwuj makro (DXY, stopy, FED) i kalendarz; wyjdź lub zmniejsz pozycję, jeśli setup się załamie lub wynik wydarzenia przeczy ocenie.", PDF_FONT, SMALL, indent=4, max_len=72)
    space(5)

    # ---------- Kontekst makro i aktywne sygnały ----------
    c.setFillColorRGB(*RGB_ACCENT)
    c.setFont(PDF_FONT_BOLD, HEAD)
    c.drawString(margin, y, "3. Kontekst makro i aktywne sygnały")
    y -= LINE * 1.2
    c.setFillColorRGB(*RGB_TEXT)
    c.setFont(PDF_FONT, SMALL)
    if makro.get("DXY") and isinstance(makro["DXY"], dict):
        dxy = makro["DXY"].get("value", "–")
        us10 = makro.get("US10Y", {}).get("value", "–")
        yc = makro.get("YIELD_CURVE")
        yc_str = f"{yc:+.2f}" if isinstance(yc, (int, float)) else str(yc)
        c.drawString(margin, y, f"DXY: {dxy}  |  US10Y: {us10}%  |  Krzywa dochodowości: {yc_str}")
        y -= LINE
    if makro.get("FEDFUNDS") and isinstance(makro["FEDFUNDS"], dict):
        fed = makro["FEDFUNDS"].get("value", "–")
        oil = makro.get("OIL_WTI", {}).get("value", "–")
        c.drawString(margin, y, f"Stopy FED: {fed}%  |  Ropa WTI: ${oil}")
        y -= LINE
    space(2)
    c.setFillColorRGB(*RGB_MUTED)
    c.setFont(PDF_FONT_BOLD, SMALL)
    c.drawString(margin, y, "Aktywne sygnały (score i siła rekomendacji)")
    y -= LINE
    c.setFillColorRGB(*RGB_TEXT)
    top = [x for x in (wyniki or []) if x.get("conviction") in ("WYSOKI", "UMIARKOWANY")][:6]
    for w in top:
        bias = w.get("meta_bias", "")
        if bias == "BUY":
            kier = "KUPNO"
        elif bias == "SELL":
            kier = "SPRZEDAZ"
        else:
            kier = "neutralnie"
        c.drawString(margin, y, f"  {w.get('instrument','')}  {kier}  Score: {w.get('lacznie',0)}/100  {w.get('conviction','')}  |  {w.get('meta_type','')}  {w.get('meta_horizon','')}")
        y -= LINE
    if not top:
        c.drawString(margin, y, "  Brak sygnałów o wysokiej/umiarkowanej sile – nie wymuszaj ekspozycji.")
        y -= LINE
    space(5)

    # ---------- Disclaimer po polsku ----------
    c.setFillColorRGB(*RGB_MUTED)
    c.setFont(PDF_FONT, 8)
    disc = (
        "Raport ma charakter informacyjny i nie stanowi porady inwestycyjnej. "
        "Handel CFD i FX wiąże się z wysokim ryzykiem. Wyniki w przeszłości i dane COT nie gwarantują przyszłych rezultatów. "
        "Wykorzystaliśmy wiele warstw (COT, reżim, flow, zaskoczenia makro, sentyment, wiadomości, wydarzenia), aby wesprzeć wniosek; "
        "żadna metoda nie daje jednak pewności. Korzystaj na własną odpowiedzialność. SofikaMax Agent."
    )
    for frag in _wrap(disc, 90):
        if _new_page_needed(y, 25):
            page_break()
            c.setFillColorRGB(*RGB_MUTED)
        c.drawString(margin, y, frag[:95])
        y -= LINE * 0.85
    y -= LINE
    c.setFillColorRGB(*RGB_TEXT)
    c.setFont(PDF_FONT, 8)
    c.drawString(margin, y, "Następne raporty: 07:00 | 12:30 | 18:30 | 20:30")
    y -= LINE

    c.showPage()
    c.save()


def build_report_pdf(
    wyniki: List[Dict],
    makro: Dict,
    payload: Dict,
    output_path: Optional[str] = None,
    logo_path: Optional[str] = None,
    include_charts: bool = True,
) -> bytes:
    """
    Buduje raport PDF: język polski (KUPNO/SPRZEDAZ/CZEKAJ/RYZYKO), ciągłość z poprzednim raportem,
    uzasadnienia, wykresy, nowoczesny ciemny layout.
    """
    buffer = BytesIO()
    _draw_pdf(wyniki, makro, payload, buffer, logo_path=logo_path, include_charts=include_charts)
    data = buffer.getvalue()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(data)
    return data
