# Jak uruchomić raporty tak, żeby przychodziły jako PDF (nie jako tekst)

**Dla kogo:** jeśli na Telegramie dostajesz długą wiadomość tekstową zamiast pliku PDF do pobrania – ta instrukcja jest dla Ciebie.

---

## Krok 1: Upewnij się, że masz zainstalowany moduł do PDF

1. Otwórz **wiersz poleceń** (CMD):
   - Naciśnij klawisz **Windows** na klawiaturze.
   - Wpisz: **cmd**
   - Naciśnij Enter (albo kliknij „Wiersz polecenia”).

2. W czarnym oknie wpisz dokładnie (możesz skopiować):
   ```text
   cd c:\TradingAgent
   ```
   Naciśnij Enter.

3. Potem wpisz (albo od razu wszystkie zależności projektu):
   ```text
   py -m pip install reportlab
   ```
   *Opcja:* zamiast tego możesz wpisać `py -m pip install -r requirements.txt` – wtedy zainstalują się wszystkie moduły, w tym reportlab.

   Naciśnij Enter i poczekaj, aż na końcu pojawi się coś w stylu „Successfully installed reportlab”.

4. Zamknij okno CMD (możesz wpisać **exit** i Enter).

---

## Krok 2: Uruchom harmonogram Z APLIKACJI (launcher)

Żeby raporty o 07:00, 12:30, 18:30 i 20:30 szły jako **PDF**, harmonogram musi być uruchamiany z tej samej aplikacji, w której masz zainstalowany „reportlab”.

1. Wejdź do folderu **c:\TradingAgent** (w Eksploratorze plików).

2. Uruchom **launcher** (program z przyciskami):
   - Szukaj pliku **launcher.py**  
   **albo**
   - Skrótu / pliku .bat, którym zwykle uruchamiasz „SofikaMax Agent” (panel z przyciskami).

   *Jeśli nie wiesz jak:* kliknij prawym na **launcher.py** → „Otwórz za pomocą” → **Python** (albo wpisz w CMD: `cd c:\TradingAgent` i potem `py launcher.py`).

3. Gdy otworzy się okno z przyciskami, kliknij:
   - **„Uruchom agenta (harmonogram 4× dziennie)”**  
   (albo przycisk o podobnej nazwie – harmonogram raportów).

4. Otworzy się **nowe czarne okno (CMD)** z tekstem w stylu:
   - „SofikaMax Agent - SCHEDULER URUCHOMIONY”
   - „Harmonogram: 07:00, 12:30, 18:30, 20:30”

5. **Sprawdź w tym oknie:**
   - Jeśli widzisz: **„[OK] PDF dostępny – raporty będą wysyłane jako pliki do pobrania”**  
     → Wszystko jest ustawione dobrze. **Nie zamykaj tego okna** – niech działa do następnego raportu (np. 18:30 lub 20:30). Wtedy na Telegramie powinien przyjść **plik PDF**.
   - Jeśli widzisz: **„[!] RAPORTY BĘDĄ WYSYŁANE JAKO TEKST (bez PDF)”**  
     → Wróć do **Kroku 1** i upewnij się, że `py -m pip install reportlab` zakończyło się bez błędu. Potem **zamknij to okno CMD z harmonogramem** i uruchom harmonogram ponownie z launcher (powtórz od punktu 2).

---

## Krok 3: Poczekaj na najbliższy raport

- Raporty lecą o: **07:00**, **12:30**, **18:30**, **20:30**.
- Na Telegramie powinien przyjść **najpierw plik (PDF)**, potem krótka wiadomość.
- Jeśli znowu przyjdzie tylko długa wiadomość tekstowa, przejdź do **„Gdy nadal przychodzi tekst zamiast PDF”** poniżej.

---

## Gdy nadal przychodzi tekst zamiast PDF

1. Otwórz w notatniku (lub w Cursor) plik:
   ```text
   c:\TradingAgent\data\pdf_error.log
   ```
   *Uwaga:* Jeśli folder **data** lub plik nie istnieje, pojawi się dopiero po pierwszej nieudanej próbie wysłania PDF (np. po raporcie o 18:30). Wtedy spróbuj ponownie po kolejnym raporcie.

2. Przejdź na **sam koniec** pliku – tam jest ostatni błąd.

3. Skopiuj ostatnie kilka–kilkanaście linii i **wklej je do czatu z asystentem** (Cursor / kogo używasz) z pytaniem: „Dlaczego raport nie jest w PDF?” – na tej podstawie da się powiedzieć, co dokładnie naprawić.

---

## Krótka ściąga

| Co robisz | Efekt |
|-----------|--------|
| `py -m pip install reportlab` w folderze projektu | Instalacja modułu do generowania PDF. |
| Uruchamiasz harmonogram **z launcher** (przycisk „Uruchom agenta”) | Ten sam Python co z reportlab = raporty jako PDF. |
| Zamykasz okno CMD z harmonogramem | Raporty się nie wyślą o 07:00, 12:30, 18:30, 20:30 – musisz znowu włączyć harmonogram z launcher. |
| Sprawdzasz `data\pdf_error.log` | Dowiesz się, dlaczego tym razem nie wygenerował się PDF. |

---

*SofikaMax Agent – instrukcja dla użytkownika.*
