# SofikaMax Agent – analiza wad i kierunki ulepszeń

Dokument: przegląd systemu pod kątem skuteczności, uczenia, analizy historii (wydarzenia, wykresy, współczynniki) oraz oczekiwań wobec doradcy.

---

## 1. Obecne słabości (wady)

### 1.1 Uczenie i weryfikacja
- **Tylko outcome rynkowy** – trafiony/nietrafiony po 14 dniach. Brak feedbacku od użytkownika (np. „przydatne / nie”, „za długi komentarz”, „ignoruję GOLD”).
- **Agregacja tylko po `situation_type`** – nie ma analizy wg poziomu conviction („gdy mówiliśmy WYSOKI, trafność była X%”) ani wg warstw („gdy COT i flow się zgadzały vs gdy nie”).
- **Stałe progi 55% / 45%** – „działa”/„nie działa” na sztywno; brak kalibracji (np. przedział ufności, minimalna liczba obserwacji).
- **Jeden horyzont (14 dni)** – brak weryfikacji na 7d, 21d, 1M; brak porównania „co sprawdzało się przy krótszym vs dłuższym horyzoncie”.

### 1.2 Historia i wydarzenia
- **Brak kontekstu wydarzeń przy sygnale** – przy zapisie sygnału nie zapisujemy: czy w dniu raportu było NFP/FOMC/CPI, jaki był `event_risk_level`, nazwy nadchodzących wydarzeń. Nie da się później odpowiedzieć: „sygnały w dni z FOMC miały trafność X%”.
- **Kalendarz tylko „na przód”** – używamy ryzyka eventowego do kary, ale nie mamy bazy „co faktycznie się wydarzyło” i jak to korelowało z wynikami par.
- **Brak replayu historycznego** – nie ma symulacji „gdybyśmy stosowali te reguły w przeszłości” (backtest / walk-forward).

### 1.3 Wykresy i czynniki techniczne
- **Regime tylko „tu i teraz”** – 40 EMA, ATR, HH/HL są liczone na bieżąco; nie zapisujemy ich przy sygnale ani nie analizujemy „w podobnym reżimie historycznie trafność była X”.
- **Brak kontekstu zmienności** – brak VIX lub percentyla ATR („zmienność wysoka/niska jak na ostatnie 12M”); brak pozycji ceny w zakresie 52w (np. „cena w górnych 10% zakresu rocznego”).
- **Brak „analogów”** – nie szukamy historycznie podobnych setupów (COT + cykl + regime) i nie pokazujemy „ostatnie 3 razy gdy było tak jak teraz, wynik był …”.

### 1.4 Scoring i transparentność
- **Stałe wagi warstw** – COT, cykl, flow, surprise, sentiment, news mają sztywne udziały; system nie uczy się, które warstwy w ostatnich miesiącach lepiej przewidywały.
- **Conviction bez kalibracji** – WYSOKI/UMIARKOWANY/NISKI nie mają przypisanej historycznej trafności (np. „WYSOKI w ostatnim roku = 58% trafionych”).
- **Świeżość danych** – brak jawnej informacji „COT z X dni temu”, „FRED z Y”, „ostatnia aktualizacja flow”; użytkownik nie wie, na jak świeżych danych opiera się raport.

### 1.5 Doradztwo i zaufanie
- **Brak kwantyfikacji niepewności** – brak formuł w stylu „szacowana trafność w tym typie sytuacji: 50–60%” lub „wysoka niepewność z powodu nadchodzącego NFP”.
- **Brak jasnego „co by zrobił doradca”** – workflow mówi „co handlować i jak długo”, ale nie ma sekcji „rekomendowana wielkość pozycji / max 1 pozycja w tej grupie” w jednym miejscu.
- **Różne źródła prawdy** – część informacji w konsoli, część w payload/Telegram/dashboard; brak jednego spójnego „raportu doradcy” z metadanymi (data, wersja, źródła danych).

---

## 2. Kierunki ulepszeń

### 2.1 Głębsze uczenie z rynkiem i z użytkownikiem
- **Kalibracja conviction** – agregacja wg `conviction` (WYSOKI/UMIARKOWANY/NISKI): dla każdego poziomu podawać historyczną trafność i liczbę obserwacji; w raporcie: „WYSOKI: 58% trafionych (n=24)”.
- **Agregacja wg warstw** – np. „gdy COT i flow w zgodzie: 62% trafionych; gdy w rozbieżności: 42%”; wykorzystać do rekomendacji (np. wymagać zgodności przed WYSOKIM conviction).
- **Feedback użytkownika (opcjonalnie)** – przycisk/komenda „sygnał przydatny / nie” lub „ignoruję ten instrument”; zapis w DB i uwzględnienie w priorytetach/workflow (np. „historycznie użytkownik najczęściej działał na EUR/AUD”).
- **Wiele horyzontów weryfikacji** – zapisywać outcome dla T+7, T+14, T+21 (lub T+1M); w feedbacku pokazywać „trafność 7d vs 14d vs 21d” i dopasować horyzont w workflow do tego, co lepiej się sprawdza.

### 2.2 Historia i wydarzenia
- **Kontekst wydarzeń przy zapisie sygnału** – w `signals` dodać kolumny: `event_risk_level`, `event_high_count`, `upcoming_events_summary` (np. „NFP, FOMC”). Dzięki temu później: „trafność gdy event_risk WYSOKI: X%”, „trafność w dni bez high impact: Y%”.
- **Baza „co się wydarzyło”** – po dacie wydarzenia zapisywać (data, waluta, typ np. NFP, wynik vs prognoza jeśli dostępne); w raporcie lub w RAG: „ostatnie NFP: +X vs prognoza Y”.
- **Korelacja wydarzenie → wynik** – analiza typu „sygnały wystawione 1–2 dni przed NFP miały trafność Z%” i używanie tego do ostrzeżeń (np. „historycznie przed NFP trafność spada – zalecana ostrożność”).

### 2.3 Wykresy i czynniki
- **Zapis kontekstu technicznego przy sygnale** – dla każdego sygnału zapisywać: `regime_type`, `ema_above_below`, `atr_percentile` (jeśli dodamy), `range_52w_pct` (pozycja w zakresie 52w). Umożliwi to analizy „w reżimie TRENDING BULLISH trafność X%”.
- **Percentyl ATR / zmienność** – np. ATR(14) / średnia(ATR z ostatnich 52 tygodni); w raporcie: „zmienność EUR: 90. percentyl (wysoka)”. Opcjonalnie VIX dla kontekstu equity/risk.
- **„Podobne sytuacje” (analogi)** – na podstawie `situation_id` + wybranych zmiennych (COT momentum, regime, flow) wyszukiwać w historii N ostatnich podobnych sygnałów i pokazywać: „Ostatnie 5 podobnych setupów: 3 trafione, 2 nietrafione”.

### 2.4 Scoring i transparentność
- **Świeżość danych** – w payload/raporcie/dashboard: „COT: dane z 2026-02-11”, „FRED: zaktualizowane 2026-02-20”, „Flow: na podstawie notowań z 2026-02-21”. Przy starych danych – krótka adnotacja (np. „COT opóźniony – uwzględnij przy decyzji”).
- **Opcjonalna adaptacja wag** – okresowo (np. co kwartał) liczyć trafność per warstwa (COT vs flow vs surprise itd.) i proponować nowe wagi lub „rekomendowane wagi na podstawie ostatnich 6M”; domyślnie wagi stałe, zmiana tylko z zatwierdzeniem użytkownika.
- **Jedna „karta doradcy”** – sekcja raportu (i payload): „Rekomendacja doradcy: 1) Max 2 pozycje z grupy EUROPA. 2) EUR, AUD na czoło; horyzont 2–4 tyg. 3) Przed NFP (piątek) zmniejsz ekspozycję. 4) Historyczna trafność w tym typie sytuacji: ok. 55% (n=12). Źródła: COT z …, FRED z …”.

### 2.5 Niepewność i jakość
- **Przedział / jakość** – przy każdym sygnale lub przy conviction: „szacowana trafność w tym typie sytuacji: 50–62% (na podstawie n=15)” lub „za mało danych – trafność nieoszacowana”.
- **Oznaczenie „niska pewność”** – gdy event_risk wysoki lub regime RANGE lub mało obserwacji dla danego situation_type: jawnie w workflow/komentarzu: „niska pewność – czekaj na potwierdzenie / mniejsza pozycja”.

---

## 3. Czego oczekiwałbym od doradcy (synteza)

1. **Rzetelność** – wiadomo, skąd dane (COT, FRED, kalendarz), kiedy były zaktualizowane, jakie są ograniczenia („COT nie jest prognozą”, „historyczna trafność X%”).
2. **Kontekst historyczny** – nie tylko „teraz EUR jest LONG”, ale „w podobnych sytuacjach (COT + reżim) trafność była Y%” oraz „przed NFP historycznie trafność spada”.
3. **Wydarzenia** – jasno: co nadchodzi (NFP, FOMC, CPI), jak to wpływa na ryzyko (kara, ostrzeżenie) i ewentualnie krótko „ostatnie NFP: wynik vs prognoza”.
4. **Wykresy i reżim** – czy trend jest potwierdzony (np. 40 EMA weekly), czy range, czy zmienność wysoka; jedna linijka per instrument w stylu „EUR: powyżej 40 EMA, trend up, ATR w normie”.
5. **Jedna, spójna rekomendacja** – „co robić, na co uważać, max ile pozycji, gdzie priorytet”; bez rozjazdu między konsolą a Telegramem a dashboardem.
6. **Uczenie się** – doradca pokazuje „co ostatnio się sprawdzało, co nie” i dostosowuje ostrożność (learned conviction, priorytet sytuacji z wyższą trafnością).
7. **Nie przeceniać** – jasne „szacowana trafność 50–60%”, „niska pewność” przy eventach/range; unikanie wrażenia „wiem na pewno”.

---

## 4. Proponowana kolejność wdrożeń (priorytet)

| Priorytet | Obszar | Działanie | Wysiłek |
|-----------|--------|-----------|---------|
| 1 | Wydarzenia + sygnały | Zapisywać przy sygnale: event_risk_level, event_high_count, krótki upcoming_events | Niski |
| 2 | Kalibracja conviction | Agregacja outcome wg conviction; w raporcie „WYSOKI: X% (n=…)” | Niski |
| 3 | Świeżość danych | W payload/raport: daty ostatniej aktualizacji COT, FRED, flow | Niski |
| 4 | Kontekst techniczny przy sygnale | Zapisać regime_type, powyzej_ema przy save_signals | Niski |
| 5 | Analiza „event vs trafność” | Nowa funkcja: trafność wg event_risk_level / w dni z high impact | Średni |
| 6 | Wiele horyzontów (7d/14d/21d) | Rozszerzyć outcome_tracker o wiele dat weryfikacji | Średni |
| 7 | Analogi (podobne sytuacje) | Zapytanie do historii: ostatnie N sygnałów z tym samym situation_id + podobny regime; pokazać trafność | Średni |
| 8 | Jedna „karta doradcy” | Sekcja w raporcie + payload: rekomendacja + źródła + szac. trafność | Średni |
| 9 | Percentyl ATR / 52w range | W regime lub osobny moduł; w raporcie „zmienność: X percentyl” | Średni |
| 10 | Feedback użytkownika | Opcjonalna ocena „przydatne/nie”; zapis; wpływ na priorytety | Wysoki |

---

*Dokument wygenerowany na podstawie przeglądu kodu SofikaMax Agent (main, outcome_tracker, event_calendar, regime_engine, situation_engine, feedback_analyzer, commentary, config).*
