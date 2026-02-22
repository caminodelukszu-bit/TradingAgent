# Stan obecny programu – Trading Agent (SofikaMax Agent)

**Dokument stanu naprawczego** – co program robi, skąd bierze dane, jak je analizuje i dlaczego wyświetla te właśnie dane.

---

## 1. Czym jest program

**Trading Agent** to system analizy rynków FX/surowce/krypto, który:

- Pobiera dane z wielu zewnętrznych źródeł (CFTC, FRED, ForexFactory, NewsAPI, yfinance, MyFXBook itd.).
- Przetwarza je przez **6 warstw analitycznych** (COT, reżim/cykl, flow, surprise, sentiment, news) plus ryzyko wydarzeń.
- Oblicza **scoring per instrument** (0–100), **conviction** (WYSOKI/UMIARKOWANY/NISKI), **bias** (BUY/SELL/NEUTRAL).
- Tworzy **jednoznaczną decyzję** (NIE WCHODŹ / WCHODŹ Z OGRANICZENIAMI / MOŻESZ WCHODZIĆ), uzasadnienie, workflow i sugerowane pary.
- Wysyła raporty na **Telegram** (PDF + krótka wiadomość) o stałych godzinach.
- Udostępnia **Dashboard** (Streamlit) z historią raportów, wykresami, archiwum i możliwością wygenerowania raportu na żądanie.

---

## 2. Główne ścieżki działania

| Ścieżka | Trigger | Efekt |
|--------|---------|--------|
| **Harmonogram** | `scheduler.py` – 07:00, 12:30, 18:30, 20:30 | `generuj_raport(tryb=PORANNY/POLUDNIOWY/...)` → `wyslij_raport()` → Telegram (PDF + wiadomość) + zapis do archiwum + zapis do cache |
| **Ręcznie (konsola)** | `python main.py` | `generuj_raport(tryb=TESTOWY)` – tylko wydruk w konsoli, bez wysyłki |
| **Launcher** | `launcher.py` – przycisk „Wyślij raport teraz” | Jak harmonogram, ale tryb TESTOWY |
| **Dashboard** | Przycisk „Odśwież raport (pobierz dane)” | `generuj_raport(tryb=STANDARDOWY)` → wyniki w sesji + zapis do archiwum |
| **Dashboard (auto)** | Wejście na stronę bez raportu w sesji | Odczyt **cache** ostatniego raportu (jeśli był wysłany z harmonogramu w ostatnich 6 h) – ten sam raport co na Telegramie |

Raport jest **jeden** w sensie pipeline’u: te same dane wejściowe, te same warstwy, ten sam scoring. Różni się tylko tryb etykietą (PORANNY/POLUDNIOWY/STANDARDOWY/TESTOWY) i tym, czy idzie na Telegram / do archiwum / do cache.

---

## 3. Skąd program pobiera dane

Dane są pobierane **przy każdym** wywołaniu `generuj_raport()` (nie na bieżąco w tle). Źródła:

### 3.1 Dane makroekonomiczne (USA / globalne)

- **Źródło:** API **FRED** (Federal Reserve Economic Data).
- **Konfiguracja:** `config.FRED_API_KEY`.
- **Serie:** DXY (dolar), US10Y, US2Y, FEDFUNDS, CPI, UNRATE, GDP, OIL_WTI.
- **Moduł:** `macro_engine.py` – `get_fred()`, `analyze_macro()`.
- **Archiwum:** opcjonalnie `history_archive` – najpierw odczyt z bazy, przy braku danych pobranie z API i zapis.
- **Po co:** Kontekst makro (kierunek dolara, stopy, krzywa dochodowości, inflacja), składnik **macro_score** w Layer 2 i kontekst dla decyzji.

### 3.2 COT (Commitment of Traders)

- **Źródło:** API **CFTC** (publicreporting.cftc.gov) – dwie bazy: waluty (jun7-fc8e), towary (6dca-aqww).
- **Moduł:** `cot_engine.py` – `get_cot_data()`, `analyze_cot()`.
- **Mapowanie:** EUR→EURO FX, GBP→BRITISH POUND, JPY, AUD, CAD, CHF, NZD, GOLD, SILVER, OIL, COPPER.
- **Archiwum:** `cot_archive` – najpierw odczyt, przy braku/niekomplecie – API + zapis.
- **Po co:** Pozycje net non-commercial (spekulanci) – **Layer 1**, score 0–20, bias BUY/SELL, ekstrema 1Y, dynamika 3–4 tyg. **BTC nie ma COT** – do scoringu używany jest flow (Layer 3).

### 3.3 Intermarket Flow (ETF)

- **Źródło:** **yfinance** – ceny ETF (GLD, TLT, SPY, UUP, USO, EEM, FXE, FXB, FXY itd.).
- **Moduł:** `flow_engine.py` – `pobierz_dane_etf()`, `analizuj_flow()`.
- **Archiwum:** `history_archive` – flow OHLC.
- **Po co:** **Layer 3** – risk-on/risk-off, kierunek USD, kierunek surowców, score 0–20 per waluta, dywergencje; dla BTC – trend i bias (gdy brak COT).

### 3.4 Reżim rynkowy (techniczny)

- **Źródło:** **yfinance** – ceny tygodniowe (Weekly) par FX i metali (np. EURUSD=X, GC=F).
- **Moduł:** `regime_engine.py` – `analizuj_wszystkie_rezimy()`.
- **Logika:** 40 EMA weekly, HH/HL (higher high / higher low), ATR (percentyl 52w), wykrywanie **range** (kara -10).
- **Po co:** **Layer 2** (część „regime”) – score techniczny 0–20, typ reżimu (TRENDING BULLISH/BEARISH, RANGE), ostrzeżenie RANGE obniża skłonność do wejścia.

### 3.5 Cykl ekonomiczny (faza / zegar)

- **Źródło:** Wskaźniki z **FRED** (np. CLI – Composite Leading Indicator) lub logika uproszczona per waluta.
- **Moduł:** `cycle_engine.py` – `get_cycle_phase()`.
- **Po co:** **Layer 2** – faza (RECOVERY, EXPANSION, SLOWDOWN, CONTRACTION), „zegar” (DEFLATION/REFLATION itd.), score 0–20. Tylko dla walut FX (nie dla GOLD/SILVER/BTC).

### 3.6 Zaskoczenia makro (Surprise)

- **Źródło:** **FRED** – historyczne serie (np. CPI, GDP) do porównania z oczekiwaniami / trendem.
- **Moduł:** `surprise_engine.py` – `get_fred_series()`, `analyze_surprise()`.
- **Archiwum:** `history_archive` (FRED).
- **Po co:** **Layer 4a** – czy dane wyszły lepiej/gorzej niż „oczekiwania” (trend), score 0–20, bias dla waluty.

### 3.7 Sentiment retail (kontrarianski)

- **Źródło:** **MyFXBook** – dane pozycji retail (long/short) przez API.
- **Konfiguracja:** `config.MYFXBOOK_EMAIL`, `MYFXBOOK_PASSWORD`. Limit ~100 zapytań/24h.
- **Moduł:** `sentiment_engine.py` – `get_outlook_cache()`, `analyze_sentiment()`.
- **Fallback:** Gdy brak MyFXBook – opcjonalnie **Claude** na podstawie nagłówków newsów (`config.CLAUDE_SENTIMENT_FALLBACK`).
- **Po co:** **Layer 4b** – kontrarianizm (wysoki long retail → bias SELL), score 0–20.

### 3.8 Wiadomości (News) i ryzyko geopolityczne

- **Źródło:** **NewsAPI** – artykuły po słowach kluczowych (waluta, „forex”, „economy” itd.).
- **Moduł:** `news_engine.py` – `pobierz_newsy()`, `oblicz_nps()`, `analyze_news()`.
- **Preferowane źródła:** Reuters, AP, BBC, Guardian, NYT, WSJ itd. (`config.NEWS_PREFERRED_SOURCES`).
- **Po co:** **Layer 5** – NPS (kierunek/siła sentymentu z nagłówków), score 0–20, **detekcja ryzyka geopolitycznego** (słowa typu „emergency”) – kara do -10 pkt i alert.

### 3.9 Kalendarz wydarzeń (event risk)

- **Źródło:** **ForexFactory** – bezpłatny kalendarz (URL: faireconomy.media/ff_calendar_thisweek.json).
- **Fallback:** Ręczny kalendarz w `event_calendar.py` (_get_manual_calendar).
- **Moduł:** `event_calendar.py` – `get_calendar()`, `analyze_event_risk()`, `get_upcoming_events_summary()`.
- **Wagi:** high=3, medium=1, low=0. Dla USD: NFP, CPI, FOMC, GDP itd.
- **Po co:** **Layer 6** – kara punktowa (np. -15 / -20) przed ważnymi wydarzeniami; poziom ryzyka (NISKI/ŚREDNI/WYSOKI/KRYTYCZNY). Dla GOLD/SILVER/BTC kara ograniczona do -10.

### 3.10 Inne (opcjonalne)

- **Money.net:** globalne stopy (gdy `config.MONEY_NET_API_KEY` ustawiony) – wyświetlane w raporcie tekstowym.
- **Oficjalne komunikaty (RSS):** ECB, FED, BOE, NBP – moduł `official_sources.py`, pobierane ręcznie lub przez Dashboard („Pobierz najnowsze komunikaty”); używane do kontekstu i zakładki Źródła w Dashboard.
- **Claude (Anthropic):** analiza historyczna archiwum raportów (`claude_analyzer.py`), opcjonalnie sentiment z newsów. Wymaga `config.CLAUDE_API_KEY`, `CLAUDE_ENABLED`.
- **RAG / LLM:** `rag_store.py` – kontekst dla komentarza analityka; `commentary_engine` – generowanie komentarza (wymaga `config.LLM_API_KEY` itd.).

---

## 4. Jak program analizuje dane (scoring i decyzje)

### 4.1 Kolejność w main.py

1. **Dane globalne (jednorazowo):** makro (FRED), flow (ETF), reżimy (Weekly), sentiment cache (MyFXBook).
2. **Per instrument (EUR, GBP, JPY, AUD, CAD, CHF, GOLD, SILVER, BTC):**
   - Layer 1: COT (albo dla BTC – flow).
   - Layer 2: cykl (tylko FX) + reżim techniczny (z `regime_engine`) + makro (wspólne).
   - Layer 3: flow per waluta (z globalnego flow).
   - Layer 4a: Surprise (tylko FX).
   - Layer 4b: Sentiment.
   - Layer 6: Event risk (dla FX = ta waluta, dla GOLD/SILVER/BTC = USD).
   - Layer 5: News.
3. **Scoring:** `oblicz_scoring()` łączy: COT (0–20), Layer 2 (cykl + regime + makro, do 20), flow (0–20), surprise (0–20), sentiment (0–20), news (0–20), odejmuje **kary** (event, range, dywergencja, OI falling).
4. **Conviction:** na podstawie łącznego score’u – progi z `config`: CONVICTION_HIGH (80), CONVICTION_MODERATE (60), CONVICTION_LOW (40).
5. **Sytuacje i meta:** `definiuj_sytuacje()`, `generuj_meta_tagi()` – typ sygnału (CORRECTION, TREND, RANGE), horyzont (np. 2–4w), warianty A/B.
6. **Pary:** `generuj_pary_walutowe()`, `generuj_pary_vs_usd()` – filtrowanie grup korelacyjnych, par wykluczonych, par lustrzanych; siła sygnału.
7. **Uczenie:** `save_signals()`, `update_outcomes()` – zapis sygnałów do `outcome_tracker`, weryfikacja hit/miss (7/14/21 dni); `analyze_feedback()`, `apply_learned_conviction()` – obniżenie conviction dla typów sytuacji o niskiej trafności.
8. **Ryzyko portfela:** `oblicz_ryzyko_portfela()` – max pozycje, max w grupie, ekspozycja per waluta; rekomendacja i ostrzeżenia.
9. **Workflow:** `build_workflow()` – lista „co i jak długo handlować”, z size i rationale.
10. **Instrukcja:** `build_instruction()` – **decyzja** (NIE WCHODŹ / WCHODŹ Z OGRANICZENIAMI / MOŻESZ WCHODZIĆ), reasons, top_ideas, ryzyka.
11. **Desk (opcjonalnie):** `run_desk_cycle()` – sugerowane zlecenia (bez wykonania w raporcie).
12. **Komentarz, karta doradcy, Claude, RAG** – dopełnienie payloadu.

Wyniki sortowane są po **lacznie** (score 0–100) malejąco. To określa kolejność instrumentów w tabelach i „top sygnały”.

### 4.2 Dlaczego wyświetlane są właśnie te dane

- **Tabela „scoring per waluta”:** wszystkie instrumenty z `INSTRUMENTY`, bo każdy przechodzi te same warstwy; kolejność = siła sygnału (lacznie).
- **Decyzja (NIE WCHODŹ / …):** wynik `build_instruction()` – bierze pod uwagę: liczbę sygnałów WYSOKI/UMIARKOWANY, ryzyko portfela, event risk, feedback (co działa/nie działa), jakość sytuacji.
- **Top pary / workflow:** filtrowane po conviction, grupach korelacyjnych, wykluczeniach (np. GOLD/SILVER nie łączone z FX), parach lustrzanych; wyświetlane są te z najwyższą siłą i spełnieniem limitów.
- **Karty transakcyjne:** tylko instrumenty z conviction WYSOKI lub UMIARKOWANY; warianty A/B i horyzont z meta tagów (COT + cykl + surprise + event).

---

## 5. Gdzie i jak wyświetlane są dane

### 5.1 Telegram

- **Wywołanie:** `telegram_bot.wyslij_raport(wyniki, makro, tryb, payload=payload)` (z schedulera lub launcher).
- **Kolejność wysyłki:**  
  1. Krótka zapowiedź: „Raport w załączniku PDF poniżej”.  
  2. Plik **PDF** (`report_pdf.build_report_pdf()`): logo, data, decyzja, sygnały, makro, ciągłość z poprzednim raportem (continuity_narrative), analiza kwartalna (quarter_analysis), wykresy (report_charts).  
  3. Jeśli PDF się nie wygeneruje – komunikat błędu + **awaryjnie** pełna wiadomość tekstowa (`formatuj_raport_telegram`).  
  4. Krótka wiadomość z decyzją (gdy PDF OK).  
  5. Opcjonalnie załącznik .md (`wyslij_plik_md=True`).  
  6. Zapis do **archiwum** (`report_archive.save_report`) – data, godzina, decyzja, summary (sygnały, makro, reasons, ryzyka).  
  7. Zapis **cache** pełnego raportu (`report_cache.save_report_cache`) – żeby Dashboard mógł go załadować bez ponownego generowania.

- **Odbiorcy:** `get_recipients()` – subskrybenci z bazy `subscription_store` lub, przy pustej bazie, `AUTORYZOWANI` z `telegram_bot.py`.

### 5.2 Dashboard (Streamlit)

- **Uruchomienie:** `streamlit run dashboard.py` (np. http://localhost:8501).
- **Dostęp:** opcjonalnie token lub hasło admina (`config.DASHBOARD_REQUIRE_TOKEN`, `ADMIN_PASSWORD`).
- **Raport w sesji:**
  - Przy wejściu: jeśli brak `report_data`, ładuje **ostatni raport z cache** (`report_cache.load_report_cache`, max 6 h) – ten sam co z harmonogramu na Telegramie.
  - Przycisk „Odśwież raport (pobierz dane)” wywołuje `generuj_raport(tryb=STANDARDOWY)` i zapisuje wynik do `st.session_state.report_data` oraz do archiwum (`_save_report_to_archive`).
- **Zakładki:** zawsze widoczne (Strona główna, Kursy & Wykresy, Przegląd, Desk, Siatka, Cykle, Przepływy, Niespodzianka, Pary, Info, Archiwum raportów, Źródła). Zawartość „Przegląd” i innych zależy od tego, czy jest załadowany raport (`has_report`).
- **Strona główna (bez raportu lub z raportem):** ostatni raport z **archiwum** (report_archive.list_reports), analiza kwartalna (quarter_analysis), tabela ostatnich raportów, kursy (yfinance) + wykresy (plotly), kalendarz wydarzeń (event_calendar), komunikaty oficjalne (official_sources). **Dane tu pochodzą z archiwum i zewnętrznych API, nie z jednego „live” raportu** – po harmonogramie archiwum ma wpis, więc strona główna pokazuje ostatnią decyzję i tabele.
- **Kursy i wykresy:** `_fetch_live_rates()` (yfinance), `_fetch_chart_data()` – pary z DESK_RATES (EUR/USD, GBP/USD, …). Wykresy wymagają `plotly`; przy braku plotly wyświetlana jest tabela kursów.
- **Archiwum raportów:** `report_archive` – lista, porównanie z poprzednim, wykresy decyzji i makro w czasie (plotly).
- **Źródła:** `official_sources` – pobrane komunikaty (RSS); przycisk „Pobierz najnowsze komunikaty” wywołuje `fetch_and_store()`.

### 5.3 Archiwum i cache

- **report_archive.db (SQLite):** każdy raport wysłany na Telegram (oraz raport wygenerowany z Dashboard „Odśwież raport”) zapisuje: report_date, report_time, decision, summary (JSON: sygnały, makro, reasons, ryzyka). Służy do: strony głównej Dashboardu, analizy kwartalnej, continuity narrative w PDF, porównań.
- **last_report_cache.pkl:** pełny snapshot (wyniki, makro, payload) po każdej wysyłce na Telegram. Dashboard ładuje go przy wejściu (jeśli < 6 h), żeby pokazać ten sam raport co na Telegramie bez ponownego 1–2 min generowania.

---

## 6. Konfiguracja kluczowa (config.py)

- **FRED_API_KEY** – obowiązkowy do makro.
- **MYFXBOOK_EMAIL / PASSWORD** – sentiment retail (Layer 4b); puste = neutral.
- **CURRENCIES, FUTURES, CRYPTO** – listy instrumentów (w main używane są stałe INSTRUMENTY).
- **CONVICTION_* , PENALTY_*** – progi i kary scoringu.
- **MAX_POSITIONS_*, MAX_EXPOSURE_*** – limity w risk_engine.
- **DESK_MODE, BROKER_ADAPTER, PAPER_CAPITAL** – tryb biurka (paper/live).
- **QUARTER_REPORTS_LIMIT** – ile raportów do analizy kwartalnej (np. 123 ≈ kwartał przy 4/dzień).
- **ADMIN_PASSWORD, DASHBOARD_REQUIRE_TOKEN** – dostęp do Dashboardu.
- **LLM_*, CLAUDE_*, NEWS_PREFERRED_SOURCES, OFFICIAL_FEEDS_EXTRA** – opcjonalne: komentarz, Claude, newsy, RSS.

---

## 7. Harmonogram (scheduler.py)

- **07:00** – raport poranny (generuj_raport PORANNY → wyslij_raport).
- **12:30** – raport południowy.
- **18:30** – raport wieczorny.
- **20:30** – raport nocny.

Scheduler musi być uruchomiony (`python scheduler.py`); co 30 s sprawdza `schedule.run_pending()`. Przy każdym zadaniu: pełne pobranie danych, analiza, wysyłka na Telegram, zapis do archiwum i cache – **Dashboard „auto” pokazuje ten sam raport w ciągu 6 h od wygenerowania**.

---

## 8. Podsumowanie przepływu danych

```
[Zewnętrzne API: CFTC, FRED, ForexFactory, NewsAPI, yfinance, MyFXBook]
        ↓
  generuj_raport()  ← scheduler (07:00, 12:30, 18:30, 20:30) / Dashboard „Odśwież” / main.py
        ↓
  6 warstw + event risk → scoring per instrument → conviction, pary, risk, workflow
        ↓
  build_instruction() → decision + reasons + top_ideas + ryzyka
        ↓
  payload (pary_cross, pary_usd, flow, rezimy, risk, workflow, instrukcja, …)
        ↓
  ┌─────────────────┬─────────────────────┬──────────────────────────────┐
  │ wyslij_raport() │ report_archive      │ report_cache                 │
  │ → Telegram PDF  │ → save_report()     │ → save_report_cache()        │
  │ → krótka wiad.  │ → list_reports()    │ → load_report_cache()        │
  │ → .md (opc.)    │   (Dashboard główna)│   (Dashboard auto-ładowanie) │
  └─────────────────┴─────────────────────┴──────────────────────────────┘
```

**Dlaczego użytkownik widzi te dane:** bo są wynikiem jednego, spójnego pipeline’u (te same źródła, te same warstwy, te same progi i kary); wyświetlanie to tylko inna „warstwa prezentacji” (konsola, Telegram PDF/tekst, Dashboard z archiwum/cache).
