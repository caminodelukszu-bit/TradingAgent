# Instrukcja: wdrożenie SofikaMax Report Server na Railway

Dzięki temu raporty na Telegram (07:00, 12:30, 18:30, 20:30) będą wysyłane **nawet przy wyłączonym komputerze**.

Railway to usługa, na której uruchomisz mały serwer wywoływany przez cron z internetu. Poniżej kroki od zera.

---

## Czego potrzebujesz

1. Konto na **GitHub** (jeśli go nie masz: [github.com](https://github.com) → Sign up).
2. Konto na **Railway** – już masz ([railway.com](https://railway.com/new)).
3. Zawartość pliku **`.env`** z Twojego komputera (klucze API) – będziesz je wpisywać w Railway.

---

## CZĘŚĆ 1: Wrzucenie projektu na GitHub

Railway łączy się z repozytorium GitHub, więc najpierw musisz tam wgrać folder `TradingAgent`.

### Krok 1.1: Załóż repozytorium na GitHubie

1. Wejdź na [github.com](https://github.com) i zaloguj się.
2. Kliknij **„+”** w prawym górnym rogu → **„New repository”**.
3. **Repository name:** wpisz np. `TradingAgent` (lub inną nazwę).
4. Zostaw **Public**. **Nie** zaznaczaj „Add a README file”.
5. Kliknij **„Create repository”**.
6. Na stronie repo zobaczysz adres, np. `https://github.com/TWOJ_LOGIN/TradingAgent.git` – **skopiuj go** (będzie potrzebny za chwilę).

### Krok 1.2: Wgraj kod z komputera do tego repozytorium

1. Na komputerze otwórz **PowerShell** lub **CMD**.
2. Wpisz i zatwierdź (po każdej linii Enter):

```cmd
cd c:\TradingAgent
git init
git add .
git commit -m "SofikaMax Report Server"
git branch -M main
git remote add origin https://github.com/TWOJ_LOGIN/TradingAgent.git
git push -u origin main
```

3. Zamiast `TWOJ_LOGIN/TradingAgent.git` wklej **swój** adres repo z GitHub (ten skopiowany wcześniej).
4. Przy `git push` GitHub może poprosić o logowanie – zaloguj się (przeglądarka lub token). Jeśli nie masz Gita: pobierz [git-scm.com](https://git-scm.com) i zainstaluj, potem spróbuj ponownie.

Gdy `git push` się uda, cały projekt jest na GitHubie.

---

## CZĘŚĆ 2: Połączenie Railway z GitHub

1. Wejdź na [railway.com/new](https://railway.com/new) (lub w swoim projekcie Railway).
2. Kliknij **„Deploy from GitHub repo”** (lub **„Repozytorium GitHub”** / ikonę GitHub).
3. Jeśli Railway pyta o dostęp do GitHub – **Authorize** / **Zezwól**.
4. Z listy repozytorium wybierz **TradingAgent** (lub jak nazwałeś repo).
5. Railway utworzy „projekt” i zacznie pierwsze wdrożenie. Poczekaj chwilę – pierwszy build może potrwać 1–2 minuty.

---

## CZĘŚĆ 3: Zmienne środowiskowe (klucze API)

Bez tych zmiennych raport nie wygeneruje się poprawnie (brak danych makro, Telegram itd.). Railway musi mieć te same wartości co w Twoim pliku `.env`.

1. W projekcie Railway kliknij **swoją usługę** (jedna karta z nazwą repo).
2. Wejdź w **„Variables”** (lub **„Settings”** → **Variables**).
3. Kliknij **„Add variable”** / **„New Variable”** i dodaj **po jednej** zmiennej (nazwa = lewa kolumna, wartość = prawa; wartość wklej z `.env` z komputera):

| Nazwa | Skąd wziąć wartość |
|-------|--------------------|
| `REPORT_CRON_TOKEN` | Wymyśl długi tajny ciąg, np. `SofikaMax2025TajnyToken` – **to wpisz sam**; tego samego użyjesz w cron-job.org |
| `FRED_API_KEY` | Z pliku `.env` na PC |
| `MYFXBOOK_EMAIL` | Z `.env` |
| `MYFXBOOK_PASSWORD` | Z `.env` |
| `LLM_API_KEY` | Z `.env` (może być puste) |
| `MONEY_NET_API_KEY` | Z `.env` (może być puste) |
| `CLAUDE_API_KEY` | Z `.env` (może być puste) |

**Telegram:**  
W projekcie token bota i odbiorcy są w pliku `telegram_bot.py`. Na Railway **nie** musisz ich wpisywać do Variables – działają z kodu. Jeśli kiedyś przeniesiesz token do `.env`, wtedy dodaj odpowiednią zmienną.

4. **Zapisz** (Save). Railway zrestartuje usługę z nowymi zmiennymi.

---

## CZĘŚĆ 4: Adres publiczny (domena)

1. W tej samej usłudze w Railway wejdź w **„Settings”**.
2. Znajdź sekcję **„Networking”** / **„Public Networking”**.
3. Kliknij **„Generate domain”** (lub **„Add domain”**). Railway nada adres typu:  
   `twoja-usluga-xxxx.up.railway.app`
4. **Skopiuj ten adres** (np. `https://tradingagent-xxxx.up.railway.app`).

Adres do wywołania raportu to:

```
https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_REPORT_CRON_TOKEN&type=PORANNY
```

Zastąp:
- `TWOJ_ADRES_RAILWAY` – wygenerowaną domeną (bez spacji),
- `TWOJ_REPORT_CRON_TOKEN` – dokładnie tą samą wartością co zmienna `REPORT_CRON_TOKEN` w Railway.

Sprawdzenie w przeglądarce:
- `https://TWOJ_ADRES_RAILWAY/health` → powinno zwrócić coś w stylu `{"ok": true, ...}`.
- `https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_TOKEN&type=PORANNY` → wygeneruje raport i wyśle na Telegram (odpowiedź: `{"ok": true, "type": "PORANNY"}`).

---

## CZĘŚĆ 5: Cron (cron-job.org) – wywołania o stałych godzinach

1. Wejdź na [cron-job.org](https://www.cron-job.org) i załóż konto (darmowe).
2. **Create cron job** / **Utwórz zadanie**.
3. **URL:** wklej (dostosuj token i typ):

   - Dla **07:00** (raport poranny):  
     `https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_REPORT_CRON_TOKEN&type=PORANNY`
   - Dla **12:30** (południowy):  
     `https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_REPORT_CRON_TOKEN&type=POLUDNIOWY`
   - Dla **18:30** (wieczorny):  
     `https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_REPORT_CRON_TOKEN&type=WIECZORNY`
   - Dla **20:30** (nocny):  
     `https://TWOJ_ADRES_RAILWAY/report?token=TWOJ_REPORT_CRON_TOKEN&type=NOCNY`

4. **Schedule:** ustaw czas w swojej strefie (np. Europe/Warsaw):
   - 07:00
   - 12:30
   - 18:30
   - 20:30  
   (czyli **4 osobne zadania**, każde z innym `type=...` jak wyżej).
5. Zapisz. Cron-job.org będzie wywoływał Twój adres Railway o tych godzinach – serwer wygeneruje raport i wyśle go na Telegram.

---

## Podsumowanie

| Krok | Gdzie | Co zrobić |
|------|--------|-----------|
| 1 | GitHub | Nowe repo → w `c:\TradingAgent`: `git init`, `add`, `commit`, `remote`, `push` |
| 2 | Railway | New project → Deploy from GitHub repo → wybór **TradingAgent** |
| 3 | Railway → Variables | Dodać: `REPORT_CRON_TOKEN` + wszystkie klucze z `.env` |
| 4 | Railway → Settings | Generate domain → skopiować adres |
| 5 | cron-job.org | 4 zadania (07:00, 12:30, 18:30, 20:30) z URL `/report?token=...&type=...` |

Od tego momentu raporty będą przychodzić na Telegram o tych godzinach **nawet gdy Twój komputer jest wyłączony**.  
Jeśli któryś krok nie działa (np. błąd przy `git push` lub brak domeny w Railway), napisz który dokładnie – doprecyzuję ten krok.
