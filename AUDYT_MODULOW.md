# Audyt modułów – Trading Agent

Przegląd wszystkich plików `.py`: czy są potrzebne, kto z nich korzysta, co można usunąć lub uprościć.

---

## 1. Moduł NIEUŻYWANY (można usunąć)

| Moduł | Powód |
|-------|--------|
| **test.py** | Nigdzie nie jest importowany. Zawiera jednorazowy test API CFTC (requests do publicreporting.cftc.gov). Służy tylko do ręcznego odpalania w konsoli. |

**Rekomendacja:** Usunąć `test.py` albo przenieść do folderu `tests/` / `dev/` i zostawić jako narzędzie deweloperskie. Na działanie aplikacji nie ma wpływu.

---

## 2. Moduły OPCJONALNE (aplikacja działa bez nich)

Te moduły są ładowane w `try/except` lub tylko gdy w config jest włączona dana funkcja. Można je wyłączyć (np. nie ustawiać klucza API), ale **są potrzebne** – odpowiadają za konkretne funkcje.

| Moduł | Używany przez | Kiedy potrzebny |
|-------|----------------|------------------|
| **money_net_engine** | main.py (get_global_yields) | Sekcja "Global Yields" w raporcie. Gdy `MONEY_NET_API_KEY` pusty – pomijany. |
| **rag_store** | commentary_engine (kontekst dla LLM) | Komentarz analityka z pamięcią. Gdy brak – komentarz bez RAG. |
| **claude_analyzer** | main.py, dashboard (ask_claude) | Wnioski Claude z archiwum w raporcie + "Pytaj Claude" w dashboardzie. Gdy `CLAUDE_ENABLED=False` lub brak klucza – pomijany. |
| **claude_sentiment** | sentiment_engine (fallback) | Gdy MyFXBook niedostępny i `CLAUDE_SENTIMENT_FALLBACK=True`. |
| **desk_controller** | main.py, dashboard | Desk: sugerowane zlecenia, wykonanie (paper/live). Gdy brak importu – raport bez sekcji Desk. |
| **position_tracker** | desk_controller, dashboard | Pozycje otwarte/zamknięte. Zależny od execution_engine. |
| **execution_engine** | desk_controller, position_tracker | Wykonanie zleceń i baza desk.db. Potrzebny tylko przy użyciu Desku. |
| **official_sources** | dashboard, continuity_narrative | Komunikaty ECB/FED/BOE/NBP (RSS), zakładka Źródła, podsumowanie w narrative. |

**Rekomendacja:** Żadnego nie usuwać. Są częścią funkcji opcjonalnych; bez nich te funkcje po prostu nie działają.

---

## 3. Moduły WYMAGANE (rdzeń aplikacji)

**Wejście / konfiguracja**
- **config.py** – używany wszędzie (FRED, MyFXBook, limity, ścieżki, LLM, Claude itd.).
- **main.py** – generowanie raportu; importuje silniki i buduje payload.

**Warstwy analizy (main)**
- **cot_engine** – Layer 1 COT (CFTC).
- **cot_archive** – cache COT; używany przez cot_engine.
- **macro_engine** – dane makro FRED; używany w main i w cycle_engine.
- **cycle_engine** – faza cyklu (używa macro_engine.get_fred).
- **regime_engine** – reżim techniczny (Weekly, EMA, ATR).
- **flow_engine** – Layer 3 flow (ETF, risk-on/off).
- **surprise_engine** – zaskoczenia makro.
- **sentiment_engine** – retail (MyFXBook) + opcjonalnie claude_sentiment.
- **news_engine** – newsy i NPS.
- **event_calendar** – ryzyko wydarzeń (ForexFactory).

**Agregacja i decyzje**
- **situation_engine** – definiuj_sytuacje (na podstawie COT, cyklu, surprise, reżimu, flow, scoringu).
- **meta_engine** – generuj_meta_tagi, drukuj_karte (bias, typ, horyzont, warianty A/B).
- **risk_engine** – ryzyko portfela, limity, ekspozycja.
- **outcome_tracker** – zapis sygnałów, weryfikacja hit/miss, agregacja do feedbacku.
- **feedback_analyzer** – analyze_feedback, apply_learned_conviction (na danych z outcome_tracker).
- **workflow_engine** – build_workflow (co i jak długo handlować).
- **instruction_engine** – build_instruction, get_primary_driver, build_rationale (decyzja, reasons, top_ideas).
- **commentary_engine** – komentarz analityka (używa llm_engine, rag_store).
- **llm_engine** – dostęp do LLM (OpenAI/Ollama); używany przez commentary_engine.

**Archiwum historii (wspólne dla wielu silników)**
- **history_archive** – FRED, flow OHLC, regime OHLC, news, events. Używany przez: macro_engine, surprise_engine, flow_engine, regime_engine, news_engine, event_calendar, claude_analyzer. **Potrzebny** – bez niego silniki nadal mogą brać dane z API, ale tracisz cache i spójność.

**Raport i dostawa**
- **report_archive** – zapis/odczyt raportów (SQLite). Używany przez: telegram_bot (save_report), dashboard (list_reports, archiwum), continuity_narrative, quarter_analysis.
- **report_cache** – cache ostatniego pełnego raportu (pickle). Używany przez: telegram_bot (save), dashboard (load przy wejściu).
- **report_pdf** – generowanie PDF. Używany przez telegram_bot; wewnętrznie: continuity_narrative, report_charts.
- **continuity_narrative** – ciągłość z poprzednim raportem; używa report_archive, quarter_analysis, official_sources.
- **quarter_analysis** – analiza kwartalna; używana przez dashboard i continuity_narrative.
- **report_charts** – wykresy w PDF; używane przez report_pdf.

**Telegram i harmonogram**
- **telegram_bot** – wysyłka raportu (PDF, wiadomość, archiwum, cache). Używany przez scheduler i launcher.
- **subscription_store** – subskrypcje i tokeny dashboardu. Używany przez telegram_bot i dashboard.

**Uruchomienie**
- **scheduler.py** – harmonogram 4× dziennie; wywołuje main.generuj_raport i telegram_bot.wyslij_raport.
- **launcher.py** – GUI z przyciskami (Dashboard, Telegram, harmonogram, konsola); opcjonalny.
- **start_dashboard_only.py** – cichy start tylko dashboardu; używany przez .vbs/.bat.

**Dashboard**
- **dashboard.py** – Streamlit; używa report_archive, report_cache, quarter_analysis, official_sources, event_calendar, subscription_store, outcome_tracker, position_tracker, desk_controller, claude_analyzer, config.

**Narzędzia (jednorazowe / ręczne)**
- **utilities/png_to_ico.py** – konwersja logo na ikonę; nie jest importowany przy starcie aplikacji. **Potrzebny** tylko do wygenerowania .ico i ewentualnie skrótu z logo.

---

## 4. Podsumowanie – co jest naprawdę potrzebne

- **Do usunięcia bez wpływu na działanie:** tylko **test.py** (albo przenieść do `tests/` / `dev/`).
- **Wszystkie pozostałe moduły** są w łańcuchu zależności: albo rdzeń (main → raport → Telegram/Dashboard), albo opcjonalna funkcja (Desk, Claude, Money.net, RAG, official_sources). Żaden nie jest zduplikowany ani zbędny.
- **history_archive** i **report_archive** mają różne role (dane historyczne vs. metadane raportów) – łączenie ich skomplikowałoby kod bez wyraźnej korzyści.
- **report_cache** vs **report_archive**: cache = pełny payload do szybkiego ładowania w dashboardzie; archive = metadane do listy, analizy kwartalnej, ciągłości. Oba są potrzebne.

---

## 5. Rekomendacje

1. **Usunąć lub przenieść** `test.py` – nie jest używany w żadnym imporcie.
2. **Nie usuwać** żadnego innego modułu – każdy ma przypisaną funkcję w pipeline lub w opcjonalnej feature.
3. **Opcjonalnie:** jeśli chcesz uprościć strukturę, można rozważyć:
   - przeniesienie `continuity_narrative` i `quarter_analysis` do jednego modułu „narrative” (mają wspólny kontekst report_archive) – to refaktor, nie usunięcie;
   - analogicznie `report_charts` mógłby być wewnątrz `report_pdf` – znów tylko refaktor.
4. **config.py** – zostaw jako jeden plik; rozbijanie na wiele plików konfiguracji skomplikowałoby importy bez wyraźnego zysku.

---

## 6. Szybka tabela: „Kto mnie importuje?”

| Moduł | Importowany przez |
|-------|-------------------|
| test.py | **nikt** |
| config | prawie wszystkie moduły |
| cot_engine | main |
| cot_archive | cot_engine |
| macro_engine | main, cycle_engine |
| cycle_engine | main |
| regime_engine | main |
| flow_engine | main |
| surprise_engine | main |
| sentiment_engine | main |
| claude_sentiment | sentiment_engine (fallback) |
| news_engine | main, claude_sentiment |
| event_calendar | main, dashboard, continuity_narrative |
| history_archive | macro, surprise, flow, regime, news, event_calendar, claude_analyzer |
| situation_engine | main |
| meta_engine | main |
| risk_engine | main |
| outcome_tracker | main, dashboard, feedback_analyzer |
| feedback_analyzer | main, instruction_engine |
| workflow_engine | main |
| instruction_engine | main |
| commentary_engine | main |
| llm_engine | commentary_engine |
| rag_store | commentary_engine |
| desk_controller | main, dashboard |
| position_tracker | desk_controller, dashboard |
| execution_engine | desk_controller, position_tracker |
| report_archive | telegram_bot, dashboard, continuity_narrative, quarter_analysis (via get_reports) |
| report_cache | telegram_bot, dashboard |
| report_pdf | telegram_bot |
| continuity_narrative | report_pdf |
| quarter_analysis | dashboard, continuity_narrative |
| report_charts | report_pdf |
| official_sources | dashboard, continuity_narrative |
| claude_analyzer | main, dashboard |
| money_net_engine | main |
| subscription_store | telegram_bot, dashboard, launcher |
| scheduler | (entry) – wywołuje main, telegram_bot |
| launcher | (entry) |
| start_dashboard_only | (entry via .vbs) |
| dashboard | (entry via streamlit) |
| telegram_bot | scheduler, launcher |
| utilities/png_to_ico | (ręcznie) |

Wniosek: **jedyny plik nigdzie nieużywany to test.py.** Reszta jest potrzebna.
