# =============================================================================
# launcher.py - SofikaMax Agent - Program do uruchomienia z pulpitu
# Uruchom: py launcher.py   lub dwuklik na skrócie na pulpicie
# =============================================================================

import os
import sys
import subprocess
import threading
import webbrowser
import time

# Ustaw katalog roboczy na folder z projektem (tam gdzie main.py, dashboard.py)
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Harmonogram w tle – bez dodatkowego okna
_scheduler_process = None
_scheduler_log_file = None
_btn_sched = None

try:
    import tkinter as tk
    from tkinter import messagebox, font, ttk
except ImportError:
    print("Brak tkinter. Zainstaluj Python z opcja 'tcl/tk' lub uruchom: py -m pip install tk")
    sys.exit(1)


def _is_port_open(host: str = "127.0.0.1", port: int = 8501, timeout: float = 0.5) -> bool:
    """Sprawdza, czy serwer nasluchuje na porcie (Dashboard gotowy)."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def run_streamlit():
    """
    Uruchamia Streamlit w WIDOCZNYM oknie CMD – zobaczysz ewentualne bledy
    (brak streamlit, blad importu itd.). Po ok. 6 s otwiera przegladarke.
    """
    try:
        # Wstepna weryfikacja – czy streamlit w ogole jest
        try:
            import streamlit  # noqa: F401
        except ImportError:
            return (
                "Brak modułu 'streamlit'. Zainstaluj zaleznosci dashboardu.\n\n"
                "W konsoli (w folderze c:\\TradingAgent) wpisz:\n"
                "  py -m pip install -r requirements-dashboard.txt\n\n"
                "Albo: py -m pip install streamlit pandas"
            )
        if sys.platform == "win32":
            # Widoczne CMD: uzytkownik widzi output i ewentualny blad (np. ModuleNotFoundError: streamlit)
            py_exe = sys.executable
            if " " in py_exe:
                py_exe = f'"{py_exe}"'
            cmd_line = f'start cmd /k "cd /d "{ROOT}" && {py_exe} -m streamlit run dashboard.py --server.headless true"'
            subprocess.Popen(cmd_line, shell=True, cwd=ROOT)
        else:
            subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.headless", "true"],
                cwd=ROOT,
            )
        # Za 6 s otworz przegladarke (daj czas Streamlitowi na start)
        def _open_browser():
            if _is_port_open(port=8501):
                webbrowser.open("http://localhost:8501")
            else:
                webbrowser.open("http://localhost:8501")  # i tak – uzytkownik moze odswiezyc
        root = getattr(tk, "_default_root", None)
        if root:
            root.after(6000, _open_browser)
        else:
            time.sleep(6)
            _open_browser()
        return True
    except Exception as e:
        return str(e)


def _scheduler_is_running():
    """Czy proces schedulera w tle nadal dziala."""
    global _scheduler_process
    return _scheduler_process is not None and _scheduler_process.poll() is None


def stop_scheduler():
    """Zatrzymuje harmonogram dzialajacy w tle i zamyka log."""
    global _scheduler_process, _scheduler_log_file, _btn_sched
    try:
        if _scheduler_process and _scheduler_process.poll() is None:
            _scheduler_process.terminate()
            try:
                _scheduler_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _scheduler_process.kill()
    except Exception:
        pass
    _scheduler_process = None
    if _scheduler_log_file:
        try:
            _scheduler_log_file.close()
        except Exception:
            pass
        _scheduler_log_file = None
    if _btn_sched:
        try:
            _btn_sched.config(text="Uruchom agenta (harmonogram 4× dziennie)")
        except Exception:
            pass


def run_scheduler_background():
    """Uruchamia scheduler w tle BEZ zadnego okna. Log do data/scheduler.log. Ten sam Python co launcher – PDF dziala."""
    global _scheduler_process
    global _scheduler_log_file
    global _btn_sched
    try:
        if _scheduler_is_running():
            return True
        stop_scheduler()
        data_dir = os.path.join(ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, "scheduler.log")
        _scheduler_log_file = open(log_path, "a", encoding="utf-8")
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        _scheduler_process = subprocess.Popen(
            [sys.executable, "scheduler.py"],
            cwd=ROOT,
            stdout=_scheduler_log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if _btn_sched:
            try:
                _btn_sched.config(text="Zatrzymaj harmonogram")
            except Exception:
                pass
        return True
    except Exception as e:
        return str(e)


def send_report_now():
    """Generuje raport i wysyla na Telegram (w watku zeby nie blokowac GUI)."""
    def _do():
        try:
            from main import generuj_raport
            from telegram_bot import wyslij_raport
            import io
            old_out = sys.stdout
            sys.stdout = io.StringIO()
            wyniki, makro, payload = generuj_raport(tryb="TESTOWY")
            sys.stdout = old_out
            wyslij_raport(wyniki, makro, "TESTOWY", wyslij_plik_md=True, payload=payload)
            root.after(0, lambda: messagebox.showinfo("SofikaMax Agent", "Raport wyslany na Telegram."))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Blad", str(e)))
    threading.Thread(target=_do, daemon=True).start()
    messagebox.showinfo("SofikaMax Agent", "Raport jest generowany i bedzie wyslany na Telegram.\nPoczekaj chwile.")


def on_dashboard():
    root = getattr(tk, "_default_root", None)
    if root:
        try:
            root.config(cursor="wait")
            root.update()
        except Exception:
            pass
    err = run_streamlit()
    if root:
        try:
            root.config(cursor="")
        except Exception:
            pass
    if err is not True:
        messagebox.showerror("Blad", f"Nie udalo sie uruchomic Dashboard:\n{err}\n\nUruchom recznie w konsoli (w folderze projektu):\npy -m streamlit run dashboard.py\n\nAlbo dwuklik: run_dashboard.bat")
    else:
        messagebox.showinfo("SofikaMax Agent", "Dashboard uruchamiany w oknie konsoli – za ok. 6 s otworzy sie przegladarka.\nJesli widzisz blad w konsoli (np. brak modułu streamlit), zainstaluj:\npy -m pip install -r requirements-dashboard.txt")


def on_telegram():
    send_report_now()


def on_scheduler():
    if _scheduler_is_running():
        stop_scheduler()
        messagebox.showinfo("SofikaMax Agent", "Harmonogram zatrzymany.")
        return
    err = run_scheduler_background()
    if err is not True:
        messagebox.showerror("Blad", f"Nie udalo sie uruchomic agenta:\n{err}")
    else:
        messagebox.showinfo("SofikaMax Agent", "Harmonogram dziala w tle – bez dodatkowych okien.\nRaporty na Telegram: 07:00, 12:30, 18:30, 20:30.\n\nLog (opcjonalnie): data\\scheduler.log\nAby zatrzymac: kliknij ponownie ten przycisk.")


def on_raport_console():
    """Uruchamia tylko generowanie raportu w konsoli (nowe okno CMD). Ten sam Python co launcher."""
    try:
        if sys.platform == "win32":
            py_exe = sys.executable
            if " " in py_exe:
                py_exe = f'"{py_exe}"'
            subprocess.Popen(
                f'start cmd /k "cd /d "{ROOT}" && {py_exe} main.py"',
                shell=True,
                cwd=ROOT,
            )
        else:
            subprocess.Popen([sys.executable, "main.py"], cwd=ROOT)
    except Exception as e:
        messagebox.showerror("Blad", str(e))


def open_management_platform():
    """Otwiera okno panelu zarządzania (subskrypcje + tokeny Dashboard). Wymaga hasła admina."""
    try:
        from config import ADMIN_PASSWORD
    except ImportError:
        ADMIN_PASSWORD = ""
    if not ADMIN_PASSWORD:
        messagebox.showwarning("SofikaMax Agent", "Ustaw ADMIN_PASSWORD w config.py, aby uzyc panelu zarzadzania.")
        return
    win = tk.Toplevel(root)
    win.title("SofikaMax Agent – Panel zarządzania")
    win.geometry("620x480")
    win.resizable(True, True)

    # Hasło na wejście
    def check_and_show():
        if pwd_var.get().strip() != ADMIN_PASSWORD:
            messagebox.showerror("Błąd", "Nieprawidłowe hasło.")
            return
        pwd_frame.destroy()
        build_tabs()

    pwd_frame = tk.Frame(win, padx=20, pady=20)
    pwd_frame.pack(fill=tk.BOTH, expand=True)
    tk.Label(pwd_frame, text="Hasło administratora", font=("Segoe UI", 11, "bold")).pack(pady=(0, 8))
    pwd_var = tk.StringVar()
    tk.Entry(pwd_frame, textvariable=pwd_var, show="*", width=25, font=("Segoe UI", 10)).pack(pady=4)
    tk.Button(pwd_frame, text="Wejdź", command=check_and_show, width=15).pack(pady=12)

    def build_tabs():
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---- Zakładka: Subskrypcje Telegram ----
        tab_subs = tk.Frame(nb)
        nb.add(tab_subs, text="Subskrypcje Telegram")
        list_frame = tk.Frame(tab_subs)
        list_frame.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(list_frame)
        lb = tk.Listbox(list_frame, height=12, font=("Consolas", 9), yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def refresh_subs():
            lb.delete(0, tk.END)
            try:
                from subscription_store import list_all
                for s in list_all():
                    status = "OK" if s["active"] else "OFF"
                    valid = s["valid_until"] or "bez limitu"
                    lb.insert(tk.END, f"  {s['telegram_id']}  |  {s['name'] or '-'}  |  do {valid}  |  {status}")
            except Exception as e:
                lb.insert(tk.END, f"  Błąd: {e}")

        refresh_subs()

        def toggle_sub():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Info", "Zaznacz wiersz.")
                return
            line = lb.get(sel[0])
            try:
                tid = int(line.strip().split("|")[0].strip())
                from subscription_store import list_all, set_active
                subs = list_all()
                active = next((s["active"] for s in subs if s["telegram_id"] == tid), None)
                if active is None:
                    return
                ok, msg = set_active(tid, not active)
                messagebox.showinfo("SofikaMax", msg)
                refresh_subs()
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        def remove_sub():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Info", "Zaznacz wiersz.")
                return
            if not messagebox.askyesno("Potwierdź", "Usunąć tego subskrybenta?"):
                return
            line = lb.get(sel[0])
            try:
                tid = int(line.strip().split("|")[0].strip())
                from subscription_store import remove_subscriber
                ok, msg = remove_subscriber(tid)
                messagebox.showinfo("SofikaMax", msg)
                refresh_subs()
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        def add_sub():
            try:
                tid = int(entry_tid.get().strip())
                name = entry_name.get().strip()
                valid = entry_valid.get().strip() or None
                from subscription_store import add_subscriber
                ok, msg = add_subscriber(tid, name=name, valid_until=valid)
                messagebox.showinfo("SofikaMax", msg)
                entry_tid.delete(0, tk.END)
                entry_name.delete(0, tk.END)
                entry_valid.delete(0, tk.END)
                refresh_subs()
            except ValueError:
                messagebox.showerror("Błąd", "Telegram ID musi być liczbą.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        btn_frame = tk.Frame(tab_subs)
        btn_frame.pack(fill=tk.X, padx=4, pady=4)
        tk.Button(btn_frame, text="Włącz / Wyłącz", command=toggle_sub, width=14).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Usuń", command=remove_sub, width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Odśwież", command=refresh_subs, width=8).pack(side=tk.LEFT, padx=2)

        add_frame = tk.LabelFrame(tab_subs, text="Dodaj subskrybenta")
        add_frame.pack(fill=tk.X, padx=4, pady=4)
        row = tk.Frame(add_frame)
        row.pack(fill=tk.X)
        tk.Label(row, text="Telegram ID:", width=12).pack(side=tk.LEFT)
        entry_tid = tk.Entry(row, width=12)
        entry_tid.pack(side=tk.LEFT, padx=2)
        tk.Label(row, text="Imię:").pack(side=tk.LEFT, padx=(8, 0))
        entry_name = tk.Entry(row, width=15)
        entry_name.pack(side=tk.LEFT, padx=2)
        tk.Label(row, text="Ważny do (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(8, 0))
        entry_valid = tk.Entry(row, width=12)
        entry_valid.pack(side=tk.LEFT, padx=2)
        tk.Button(add_frame, text="Dodaj", command=add_sub).pack(pady=4)

        # ---- Zakładka: Dostęp do Dashboard ----
        tab_tok = tk.Frame(nb)
        nb.add(tab_tok, text="Dostęp do Dashboard")
        tok_list_frame = tk.Frame(tab_tok)
        tok_list_frame.pack(fill=tk.BOTH, expand=True)
        sb2 = tk.Scrollbar(tok_list_frame)
        lb_tok = tk.Listbox(tok_list_frame, height=10, font=("Consolas", 9), yscrollcommand=sb2.set)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        lb_tok.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def refresh_tokens():
            lb_tok.delete(0, tk.END)
            try:
                from subscription_store import list_dashboard_tokens
                for t in list_dashboard_tokens():
                    status = "ważny" if t["valid"] else "wygasły"
                    lb_tok.insert(tk.END, f"  {t['token'][:16]}...  |  {t['name'] or '-'}  |  do {t['valid_until'] or 'bez limitu'}  |  {status}")
            except Exception as e:
                lb_tok.insert(tk.END, f"  Błąd: {e}")

        refresh_tokens()

        def revoke_token():
            sel = lb_tok.curselection()
            if not sel:
                messagebox.showinfo("Info", "Zaznacz wiersz.")
                return
            if not messagebox.askyesno("Potwierdź", "Odwołać ten token? Gość straci dostęp."):
                return
            try:
                from subscription_store import list_dashboard_tokens, revoke_dashboard_token
                tokens = list_dashboard_tokens()
                idx = sel[0]
                if idx >= len(tokens):
                    return
                full_token = tokens[idx]["token"]
                ok, msg = revoke_dashboard_token(full_token)
                messagebox.showinfo("SofikaMax", msg)
                refresh_tokens()
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        def create_token():
            name = entry_tok_name.get().strip()
            valid = entry_tok_valid.get().strip() or None
            try:
                from subscription_store import create_dashboard_token
                tok, msg = create_dashboard_token(name=name, valid_until=valid)
                if tok:
                    messagebox.showinfo("SofikaMax Agent", f"Token utworzony. Skopiuj go (pokazujemy raz):\n\n{tok}\n\n{msg}")
                    entry_tok_name.delete(0, tk.END)
                    entry_tok_valid.delete(0, tk.END)
                    refresh_tokens()
                else:
                    messagebox.showerror("Błąd", msg)
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        tk.Button(tab_tok, text="Odwołaj zaznaczony token", command=revoke_token).pack(anchor=tk.W, padx=4, pady=4)
        tok_add = tk.LabelFrame(tab_tok, text="Utwórz token dostępu")
        tok_add.pack(fill=tk.X, padx=4, pady=4)
        r2 = tk.Frame(tok_add)
        r2.pack(fill=tk.X)
        tk.Label(r2, text="Nazwa gościa:").pack(side=tk.LEFT)
        entry_tok_name = tk.Entry(r2, width=20)
        entry_tok_name.pack(side=tk.LEFT, padx=4)
        tk.Label(r2, text="Ważny do (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(8, 0))
        entry_tok_valid = tk.Entry(r2, width=12)
        entry_tok_valid.pack(side=tk.LEFT, padx=4)
        tk.Button(tok_add, text="Utwórz token", command=create_token).pack(pady=4)

    win.transient(root)
    win.grab_set()


def _on_closing():
    """Przy zamykaniu launchera zatrzymaj harmonogram w tle."""
    stop_scheduler()
    root.destroy()


def main():
    global root
    root = tk.Tk()
    root.title("SofikaMax Agent")
    root.resizable(False, False)
    root.geometry("380x320")
    root.protocol("WM_DELETE_WINDOW", _on_closing)

    # Tlo i czcionka
    try:
        f = font.Font(family="Segoe UI", size=10)
    except Exception:
        f = font.nametofont("TkDefaultFont")

    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="SofikaMax Agent", font=("Segoe UI", 16, "bold")).pack(pady=(0, 16))

    btn_dash = tk.Button(frame, text="Otwórz Dashboard", command=on_dashboard, width=28, height=2, font=f, cursor="hand2")
    btn_dash.pack(pady=6)

    btn_telegram = tk.Button(frame, text="Wyślij raport na Telegram teraz", command=on_telegram, width=28, height=2, font=f, cursor="hand2")
    btn_telegram.pack(pady=6)

    global _btn_sched
    _btn_sched = tk.Button(frame, text="Uruchom agenta (harmonogram 4× dziennie)", command=on_scheduler, width=28, height=2, font=f, cursor="hand2")
    _btn_sched.pack(pady=6)

    btn_console = tk.Button(frame, text="Raport w konsoli (bez Telegram)", command=on_raport_console, width=28, height=2, font=f, cursor="hand2")
    btn_console.pack(pady=6)

    btn_mgmt = tk.Button(frame, text="Panel zarządzania (subskrypcje + tokeny)", command=open_management_platform, width=28, height=2, font=f, cursor="hand2")
    btn_mgmt.pack(pady=6)

    tk.Button(frame, text="Zamknij", command=root.destroy, width=20, font=f, cursor="hand2").pack(pady=12)

    root.mainloop()


if __name__ == "__main__":
    main()
