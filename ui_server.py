"""Optional local upload UI. Run: python ui_server.py (no call until Extract clicked)."""
import json
import os
import re
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import extract
from experiment import local_key

ROOT = Path(__file__).resolve().parent
LIMIT = 32 * 1024 * 1024
TOKEN = secrets.token_urlsafe(32)
BUSY = threading.Lock()


def configure():
    if (ROOT / ".env").exists():
        os.environ["GEMINI_API_KEY"] = local_key(ROOT / ".env")
    extract.MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", extract.MODEL):
        raise ValueError("Invalid GEMINI_MODEL identifier")


def supported(data, suffix):
    return ((suffix == ".pdf" and data.startswith(b"%PDF-")) or
            (suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
            (suffix in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff")))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No report filenames, bodies or credentials in HTTP logs.

    def send(self, status, payload, kind="application/json"):
        body = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode() if kind == "application/json" else payload
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def trusted(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == expected and self.headers.get("Origin", "http://" + expected) == "http://" + expected

    def do_GET(self):
        if not self.trusted():
            return self.send(403, {"error": "Open this app using its 127.0.0.1 address."})
        if self.path == "/":
            return self.send(200, (ROOT / "ui/index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/config":
            return self.send(200, {"configured": bool(os.environ.get("GEMINI_API_KEY")), "model": extract.MODEL,
                                   "max_bytes": LIMIT, "token": TOKEN})
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        self.close_connection = True
        if self.path != "/api/extract":
            return self.send(404, {"error": "Not found"})
        if not self.trusted() or self.headers.get("X-Upload-Token") != TOKEN:
            return self.send(403, {"error": "Reload the page before uploading."})
        if not os.environ.get("GEMINI_API_KEY"):
            return self.send(503, {"error": "Configure GEMINI_API_KEY in .env and restart the app."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send(400, {"error": "Invalid upload size."})
        if not 0 < size <= LIMIT:
            return self.send(413, {"error": "Choose a nonempty file up to 32 MB."})
        suffix = Path(unquote(self.headers.get("X-Filename", ""))).suffix.lower()
        if suffix not in (".pdf", ".png", ".jpg", ".jpeg"):
            return self.send(415, {"error": "Choose a PDF, JPG or PNG report."})
        if not BUSY.acquire(blocking=False):
            return self.send(409, {"error": "Another report is processing. Please wait."})
        try:
            self.connection.settimeout(30)
            data = self.rfile.read(size)
            if len(data) != size or not supported(data, suffix):
                return self.send(400, {"error": "The file is incomplete or does not match its format."})
            with tempfile.TemporaryDirectory(prefix="lab-upload-") as directory:
                path = Path(directory) / ("report" + suffix)
                path.write_bytes(data)
                result = extract.extract(path)
            self.send(200, result)
        except RuntimeError as error:
            self.send(502, {"error": str(error)})
        except (OSError, ValueError, KeyError):
            self.send(500, {"error": "The report could not be processed. Check its format and Poppler installation."})
        finally:
            BUSY.release()


if __name__ == "__main__":
    try:
        configure()
        server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
        print("Lab report UI: http://127.0.0.1:8765 (Ctrl+C to stop)")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as error:
        raise SystemExit("UI could not start. Check .env, GEMINI_MODEL and whether port 8765 is already in use.") from None
