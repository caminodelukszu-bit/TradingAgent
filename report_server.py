# =============================================================================
# report_server.py - Serwer HTTP do wywolywania raportow przez CRON (chmura/VPS)
# Raporty 07:00, 12:30, 18:30, 20:30 mozna wyslac z zewnetrznego crona (cron-job.org)
# nawet przy wylaczonym Twoim komputerze - pod warunkiem ze ten serwer dziala
# na maszynie zawsze wlaczonej (VPS, Railway, Render itd.).
#
# Uruchomienie: py report_server.py
# Zmienne srodowiska: REPORT_CRON_TOKEN (wymagany), REPORT_SERVER_PORT (domyslnie 8765)
# Endpoint: GET /report?token=TWÓJ_TOKEN&type=PORANNY|POLUDNIOWY|WIECZORNY|NOCNY
# =============================================================================

import os
import sys
import io
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ladowanie .env
try:
    from pathlib import Path
    _env = Path(ROOT) / ".env"
    if _env.exists():
        from dotenv import load_dotenv
        load_dotenv(_env)
except Exception:
    pass

REPORT_CRON_TOKEN = os.environ.get("REPORT_CRON_TOKEN", "").strip()
# Railway i inne chmury ustawiają PORT – używamy go, gdy jest
REPORT_SERVER_PORT = int(os.environ.get("PORT", os.environ.get("REPORT_SERVER_PORT", "8765")))
ALLOWED_TYPES = ("PORANNY", "POLUDNIOWY", "WIECZORNY", "NOCNY")


class ReportHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prosty log na stderr
        sys.stderr.write("[report_server] %s - %s\n" % (self.log_date_time_string(), format % args))

    def _reply(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            self._reply(200, {"ok": True, "service": "SofikaMax Report Server"})
            return

        if path != "/report":
            self._reply(404, {"ok": False, "error": "Not found. Use GET /report?token=...&type=..."})
            return

        token = (query.get("token") or [""])[0].strip()
        report_type = (query.get("type") or [""])[0].strip().upper()

        if not REPORT_CRON_TOKEN:
            self._reply(500, {"ok": False, "error": "REPORT_CRON_TOKEN not set"})
            return
        if token != REPORT_CRON_TOKEN:
            self._reply(403, {"ok": False, "error": "Invalid token"})
            return
        if report_type not in ALLOWED_TYPES:
            self._reply(400, {"ok": False, "error": "type must be one of: " + ", ".join(ALLOWED_TYPES)})
            return

        # Generuj raport i wyslij na Telegram (w tym samym watku - cron poczeka)
        old_stdout = sys.stdout
        try:
            sys.stdout = io.StringIO()
            from main import generuj_raport
            from telegram_bot import wyslij_raport
            wyniki, makro, payload = generuj_raport(tryb=report_type)
            wyslij_raport(wyniki, makro, report_type, payload=payload)
            out = sys.stdout.getvalue()
        except Exception as e:
            sys.stdout = old_stdout
            self._reply(500, {"ok": False, "error": str(e), "type": report_type})
            return
        finally:
            sys.stdout = old_stdout

        self._reply(200, {"ok": True, "type": report_type})


def main():
    if not REPORT_CRON_TOKEN:
        print("Ustaw REPORT_CRON_TOKEN w .env (np. REPORT_CRON_TOKEN=twoj_tajny_ciag)")
        sys.exit(1)
    server = HTTPServer(("0.0.0.0", REPORT_SERVER_PORT), ReportHandler)
    print("SofikaMax Report Server: http://0.0.0.0:%s" % REPORT_SERVER_PORT)
    print("  /health  - sprawdzenie dzialania")
    print("  /report?token=...&type=PORANNY|POLUDNIOWY|WIECZORNY|NOCNY")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
