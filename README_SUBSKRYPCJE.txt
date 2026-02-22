========================================
SofikaMax Agent - Subskrypcje (kto dostaje raporty)
========================================

PELNA KONTROLA: mozesz wlaczac/wylaczac kazdego odbiorce, ustawiac date konca subskrypcji i dodawac nowych.

-- JAK TO DZIALA --
1. Lista odbiorcow raportow na Telegram = baza subskrypcji (plik subscriptions.db).
2. Jesli baza jest pusta, uzywana jest lista AUTORYZOWANI z telegram_bot.py (stare zachowanie).
3. W panelu Dashboard (zakladka "Subskrypcje") zarzadzasz kto ma dostep. Dostep chroniony haslem (config: ADMIN_PASSWORD).

-- PIERWSZE URUCHOMIENIE --
1. W config.py ustaw: ADMIN_PASSWORD = "twoje_haslo"
2. Uruchom Dashboard (Launcher -> Otworz Dashboard).
3. Jesli nie masz jeszcze raportu, przewin w dol - pojawi sie sekcja "Zarzadzanie subskrypcjami". Zaloguj sie haslem.
4. Kliknij "Importuj AUTORYZOWANI do bazy" - obecna lista z telegram_bot (np. Twoj Chat ID) trafi do bazy. Od teraz raporty ida tylko do osob z bazy.
5. Dodawaj nowych: Telegram ID (np. z @userinfobot), imie, opcjonalnie data waznosci (YYYY-MM-DD). Przycisk "Dodaj".

-- WYLACZENIE SUBSKRYPCJI --
W zakladce Subskrypcje: przy osobie kliknij "Wylacz". Przestanie dostawac raporty od razu. "Wlacz" przywraca.

-- DATA KONCA --
Przy dodawaniu mozesz podac "Wazny do" (YYYY-MM-DD). Po tej dacie osoba nie dostaje raportow (mozesz przedluzyc edytujac date).

-- WIELU KOMPUTEROW --
Plik subscriptions.db mozesz trzymac w jednym miejscu (np. na dysku sieciowym) i w config ustawic:
  SUBSCRIPTION_DB_PATH = "Z:\\SofikaMax\\subscriptions.db"
Wtedy kazdy komputer z agentem uzywa tej samej listy. Albo kopiuj subscriptions.db na drugi komputer - lista jest przenosna.

-- DOSTEP DO PLATFORMY (DASHBOARD) DLA OBCYCH --
1. W config.py ustaw: DASHBOARD_REQUIRE_TOKEN = True
2. W Dashboard zaloguj sie haslem admina -> zakladka Subskrypcje -> sekcja "Dostep do Dashboard"
3. Kliknij "Utworz token dostepu": podaj nazwe gościa (opcjonalnie) i date waznosci (YYYY-MM-DD lub puste = bez limitu)
4. Skopiuj wygenerowany token i przekaz gościowi + link do platformy (np. https://twoja-domena.pl lub localhost:8501 jesli u Ciebie)
5. Gosc wchodzi na link, wpisuje token -> ma dostep do raportow do podanej daty
6. Odwolanie: w tej samej sekcji przy tokenie kliknij "Revoke" - dostep znika od razu

-- BEZPIECZENSTWO --
- Haslo admina trzymaj tylko w config (nie wrzucaj config z haslem do repozytorium).
- Plik subscriptions.db zawiera Telegram ID i opcjonalnie imiona/emaile - traktuj jak dane wrażliwe.
- Tokeny Dashboard trzymane sa w subscriptions.db; nie udostepniaj tego pliku osobom z zewnatrz.
