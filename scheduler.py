import schedule
import time
from datetime import datetime
from main          import generuj_raport
from telegram_bot  import wyslij_raport

# Przechowuje ostatnie wyniki do Telegrama
ostatnie_wyniki = {"wyniki": [], "makro": {}}


def raport_poranny():
    print(f"\n{'#'*60}")
    print(f"  SofikaMax Agent | RAPORT PORANNY - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'#'*60}")
    wyniki, makro, payload = generuj_raport(tryb="PORANNY")
    wyslij_raport(wyniki, makro, "PORANNY", payload=payload)


def raport_poludniowy():
    print(f"\n{'#'*60}")
    print(f"  SofikaMax Agent | RAPORT POLUDNIOWY - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'#'*60}")
    wyniki, makro, payload = generuj_raport(tryb="POLUDNIOWY")
    wyslij_raport(wyniki, makro, "POLUDNIOWY", payload=payload)


def raport_wieczorny():
    print(f"\n{'#'*60}")
    print(f"  SofikaMax Agent | RAPORT WIECZORNY - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'#'*60}")
    wyniki, makro, payload = generuj_raport(tryb="WIECZORNY")
    wyslij_raport(wyniki, makro, "WIECZORNY", payload=payload)


def raport_nocny():
    print(f"\n{'#'*60}")
    print(f"  SofikaMax Agent | RAPORT NOCNY - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'#'*60}")
    wyniki, makro, payload = generuj_raport(tryb="NOCNY")
    wyslij_raport(wyniki, makro, "NOCNY", payload=payload)


# Harmonogram
schedule.every().day.at("07:00").do(raport_poranny)
schedule.every().day.at("12:30").do(raport_poludniowy)
schedule.every().day.at("18:30").do(raport_wieczorny)
schedule.every().day.at("20:30").do(raport_nocny)


def _check_pdf_available():
    """Sprawdza, czy raport moze byc wyslany jako PDF. Jesli nie – wypisuje jak naprawic."""
    try:
        from report_pdf import build_report_pdf  # wymaga reportlab
        return True
    except Exception as e:
        print("\n  [!] RAPORTY BEDA WYSYLANE JAKO TEKST (bez PDF).")
        print(f"      Przyczyna: {e}")
        print("      Aby dostawac PDF: w tym samym Pythonie uruchom:")
        print("        py -m pip install reportlab")
        print("      Nastepnie zamknij to okno i uruchom harmonogram ponownie (np. z launchera).")
        print("="*60)
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print(f"  SofikaMax Agent - SCHEDULER URUCHOMIONY")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*60)
    pdf_ok = _check_pdf_available()
    if pdf_ok:
        print("  [OK] PDF dostepny – raporty beda wysylane jako pliki do pobrania (nie jako tekst).")
    print("\nHarmonogram:")
    print("  07:00  Raport poranny")
    print("  12:30  Raport poludniowy")
    print("  18:30  Raport wieczorny")
    print("  20:30  Raport nocny")
    print("\nNie zamykaj tego okna!")
    print("Aby zatrzymac: Ctrl+C")
    print("="*60)

    # Pokaz czas do nastepnego raportu
    next_run = schedule.next_run()
    if next_run:
        delta   = next_run - datetime.now()
        godziny = int(delta.seconds // 3600)
        minuty  = int((delta.seconds % 3600) // 60)
        print(f"\nNastepny raport za: {godziny}h {minuty}min")

    # Petla glowna
    while True:
        schedule.run_pending()
        time.sleep(30)