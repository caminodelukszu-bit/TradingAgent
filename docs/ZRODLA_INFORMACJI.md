# Źródła informacji – raporty i news

## 1. Analiza kwartalna (123 raporty)

Przed wydaniem każdego bieżącego raportu system analizuje **ostatnie 123 raporty** (~1 kwartał przy 4 raporty/dzień). Nie opisuje każdego z osobna – wszystkie podlegają agregacji:

- rozkład decyzji (CZEKAJ / ostrożne wejście / wejście),
- najczęstsze rekomendowane instrumenty,
- trend makro (DXY, FED) w okresie,
- ewentualna seria CZEKAJ z rzędu.

Wynik trafia do sekcji **„Analiza kwartalna”** w PDF. Limit: `config.QUARTER_REPORTS_LIMIT` (domyślnie 123).

---

## 2. Rzetelne źródła wiadomości (2026)

Na podstawie rozmowy o najbardziej rzetelnych źródłach:

### Agencje prasowe (pierwotne źródła)

| Źródło | Uwagi | API |
|--------|--------|-----|
| **Reuters** | Bardzo neutralne, dokładne | Płatne (Refinitiv); testy przez Thomson Reuters Developer Portal / RapidAPI |
| **Associated Press (AP)** | Obiektywne, zwięzłe | AP Media API – ograniczony darmowy plan (~1000 zapytań/mies.) |
| **Agence France-Presse (AFP)** | Duża sieć korespondentów | AFP Content API – free trial, programy dla start-upów |

### Renomowane media

| Źródło | Uwagi | API |
|--------|--------|-----|
| **BBC News** | Wysoki standard relacji międzynarodowych | Dostęp przez NewsAPI / agregatory |
| **The Guardian** | Jakość dziennikarstwa, rzetelność | **Guardian Open Platform** – darmowe API (niekomercyjne/edukacyjne) |
| **The New York Times** | Kompleksowe pokrycie | **NYT Developer Network** – darmowe klucze, limity dzienne |
| **The Wall Street Journal** | Wiarygodność w biznesie i ekonomii | Przez NewsAPI / Mediastack |
| **The Economist** | Analizy geopolityczne i gospodarcze | Płatne / agregatory |

### Agregatory (wiele źródeł naraz)

| Źródło | Uwagi |
|--------|--------|
| **NewsAPI.org** | Darmowo (dev): BBC, Reuters, WSJ i inne. Obecnie używane w projekcie. |
| **Mediastack** | Darmowy plan (~100 zapytań/mies.), tysiące źródeł. |

W projekcie: **NewsAPI** + **preferowane źródła** w `config.NEWS_PREFERRED_SOURCES`. Artykuły z Reuters, AP, BBC, Guardian, NYT, WSJ itd. są sortowane na górę listy w `news_engine.pobierz_newsy`. Opcjonalnie można dodać Guardian API i NYT API (`config.GUARDIAN_API_KEY`, `NYT_API_KEY`) dla dodatkowych zapytań.

---

## 3. Źródła rządowe i G20 – czy warto obserwować?

**Tak – warto**, pod warunkiem **selektywnego filtrowania**: tylko komunikaty, które realnie mogą wpływać na rynek (stopy, fiskal, handel, sankcje, stabilność).

### Dlaczego to ma sens

- **Geopolityka → rynki**: decyzje Białego Domu, Kremla, EBC, NBP, Rady UE itd. (sankcje, stopy, pakiety pomocowe) bezpośrednio ruszają waluty i stopy.
- **G20**: USA, Chiny, UE, Japonia, UK, Niemcy, Francja, Włochy, Kanada, Australia, Indie, Rosja, Brazylia, RPA, Korea Płd., Indonezja, Meksyk, Turcja, Arabia Saudyjska, Argentyna (+ UE) – decyzje szczytów i po szczytach często wywołują zmienność.
- **Komunikaty pierwotne**: oficjalne strony rządowe i banków centralnych to źródła pierwotne; mniej zniekształceń niż w „drugim obiegu”.

### Co obserwować (selektywnie)

- **Stopy procentowe i polityka pieniężna**: FED, EBC, BOE, BOJ, NBP, BOC, SNB, RBA – komunikaty po posiedzeniach, przemówienia prezesów.
- **Fiskal i dług**: wielkość pakietów, dług publiczny, umowy handlowe (USA–Chiny, UE–UK itd.).
- **Geopolityka z wpływem na rynek**: sankcje (USA, UE, UK), embargo, wojna handlowa, kryzysy zadłużenia (np. kraje EM).
- **Energia i surowce**: OPEC+, USA (SPR, wydobycie), Rosja – komunikaty wpływające na ropę/gaz.

### Źródła techniczne (pomysł na przyszłość)

- **RSS / oficjalne API**: Biały Dom (briefings), Komisja Europejska, EBC, NBP, BOE – wiele ma kanały RSS lub sekcje „News” do skanowania.
- **Kreml / rząd Rosji**: oficjalne komunikaty (np. kremlin.ru) – filtry słów kluczowych (sankcje, gaz, ropa, wojna).
- **G20**: komunikaty po szczytach (g20.org, strony prezydencji) – zwykle 1–2 razy w roku + spotkania ministrów finansów.

Propozycja implementacji: osobny moduł (np. `official_sources.py`) z listą URL-i RSS lub endpointów, pobieraniem 1–2× dziennie, filtrowaniem po słowach kluczowych (rate, sanctions, trade, stimulus, oil, gas, debt) i zapisem do wspólnego „strumienia wiadomości” lub do event_calendar jako „komunikat oficjalny”. **Nie** wrzucać wszystkiego – tylko to, co ma jasny potencjał ruchu na rynku.

### Podsumowanie

- **123 raporty** – wdrożone: analiza kwartalna przed każdym raportem, wynik w PDF.
- **Rzetelne media** – wdrożone: preferowane źródła (Reuters, AP, BBC, Guardian, NYT, WSJ itd.) w `config` i sortowanie w `news_engine`.
- **Źródła rządowe G20** – rekomendowane jako kolejny krok: moduł oficjalnych źródeł z filtrowaniem po wpływie na rynek; bez obserwacji każdego komunikatu, tylko tych istotnych dla stóp, walut i surowców.
