# Raporty na Telegram przy wyłączonym komputerze

Żeby dostawać raporty o **07:00, 12:30, 18:30, 20:30** także wtedy, gdy **Twój komputer jest wyłączony**, raport musi być generowany **gdzieś w internecie, 24/7** (serwer, chmura), a nie na Twoim PC.

---

## Jak to działa

1. **Serwer raportów** (`report_server.py`) działa na maszynie **zawsze włączonej** (VPS, Railway, Render itd.).
2. **Zewnętrzny cron** (np. [cron-job.org](https://cron-job.org)) o ustalonych godzinach **wywołuje adres** tego serwera.
3. Serwer generuje raport i wysyła go na Telegram. Nie musisz mieć włączonego komputera.

---

## Krok 1: Gdzie uruchomić serwer (maszyna 24/7)

Potrzebujesz **jednej** z opcji:

- **VPS** (np. Oracle Cloud Free Tier, Contabo, DigitalOcean) – masz tam cały projekt, uruchamiasz `py report_server.py` (np. przez systemd lub screen).
- **Railway / Render / PythonAnywhere** – wgrywasz projekt, ustawiasz polecenie startowe: `python report_server.py`, dodajesz zmienne środowiskowe (jak niżej).

Na tym samym serwerze muszą być zainstalowane zależności (`pip install -r requirements.txt`) oraz plik **`.env`** z wszystkimi kluczami (FRED, Telegram itd.), tak jak na swoim PC.

---

## Krok 2: Token w .env

Na serwerze (lub w panelu Railway/Render) ustaw w `.env`:

```env
REPORT_CRON_TOKEN=wybrany_tajny_ciag_123
```

Ten sam ciąg podasz potem w adresie URL w cron-job.org. Port domyślny to **8765** (możesz zmienić przez `REPORT_SERVER_PORT=8765`).

---

## Krok 3: Adres do wywołania

Gdy serwer już działa, z zewnątrz będzie dostępny pod adresem typu:

- `https://twoja-domena.pl/report`  
  lub  
- `http://IP_SERWERA:8765/report`

Pełny URL z tokenem i typem raportu:

```
https://twoja-domena.pl/report?token=wybrany_tajny_ciag_123&type=PORANNY
```

Typy: **PORANNY**, **POLUDNIOWY**, **WIECZORNY**, **NOCNY**.

---

## Krok 4: Cron zewnętrzny (cron-job.org)

1. Wejdź na [cron-job.org](https://cron-job.org) i załóż (darmowe) konto.
2. Utwórz **4 zadania** (po jednym na każdy raport):

| Godzina  | URL (type=...)   |
|----------|------------------|
| 07:00    | `...?token=TWÓJ_TOKEN&type=PORANNY`     |
| 12:30    | `...?token=TWÓJ_TOKEN&type=POLUDNIOWY` |
| 18:30    | `...?token=TWÓJ_TOKEN&type=WIECZORNY`   |
| 20:30    | `...?token=TWÓJ_TOKEN&type=NOCNY`       |

3. Dla każdego zadania ustaw **czas** (np. strefa Europe/Warsaw) i zapisz.
4. Cron-job wywoła Twój serwer o tych godzinach; serwer wygeneruje raport i wyśle go na Telegram.

Uwaga: generowanie raportu może trwać 1–2 minuty. Jeśli usługa crona ma krótki limit czasu (np. 30 s), ustaw dłuższy timeout albo wybierz plan, który go pozwala wydłużyć.

---

## Test lokalny (na PC)

Żeby sprawdzić, że endpoint działa, **na swoim komputerze**:

1. W `.env` dodaj: `REPORT_CRON_TOKEN=test123`
2. Uruchom: `py report_server.py`
3. W przeglądarce wejdź na:  
   `http://127.0.0.1:8765/report?token=test123&type=PORANNY`  
   Powinien wygenerować się raport i zostać wysłany na Telegram. W odpowiedzi zobaczysz np. `{"ok": true, "type": "PORANNY"}`.

Endpoint **/health**: `http://127.0.0.1:8765/health` – zwraca `{"ok": true}` gdy serwer działa.

---

## Podsumowanie

| Sytuacja | Co użyć |
|----------|--------|
| PC **włączony** – raporty w tle, bez dodatkowego okna | Launcher → „Uruchom agenta (harmonogram 4× dziennie)” |
| PC **wyłączony** – raporty i tak mają przychodzić | Serwer `report_server.py` na VPS/chmurze + cron-job.org (4 wywołania dziennie) |

Bez uruchomienia raportów **na serwerze 24/7** i bez zewnętrznego crona nie da się wysyłać raportów przy wyłączonym komputerze – wtedy po prostu nic nie działa.
