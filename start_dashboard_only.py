# =============================================================================
# start_dashboard_only.py - SofikaMax Agent
# Cichy start: tylko przeglądarka z Dashboardem. Bez GUI, bez okien CMD, bez powiadomień.
# Uruchamiane przez Uruchom_SofikaMax_Agent.vbs (pythonw) lub .bat.
# =============================================================================

import os
import sys
import subprocess
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _is_port_open(host: str = "127.0.0.1", port: int = 8501, timeout: float = 0.3) -> bool:
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def main():
    # Sprawdź, czy streamlit jest zainstalowany
    try:
        import streamlit  # noqa: F401
    except ImportError:
        # Jedyny przypadek, gdy pokazujemy okno: błąd (potrzebny streamlit)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "SofikaMax Agent",
                "Brak modułu 'streamlit'.\n\nW konsoli (w folderze projektu) wpisz:\n"
                "  py -m pip install -r requirements-dashboard.txt"
            )
            root.destroy()
        except Exception:
            print("Brak modułu streamlit. Zainstaluj: py -m pip install -r requirements-dashboard.txt")
        sys.exit(1)

    # Uruchom Streamlit w tle BEZ okna konsoli (Windows)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.headless", "true"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    # Czekaj na gotowość serwera (max 15 s), potem otwórz przeglądarkę
    for _ in range(50):
        if _is_port_open(port=8501):
            break
        time.sleep(0.3)
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    main()
