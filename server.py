from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
DATA_FILE = BASE_DIR / "overlays.json"
HOST = "127.0.0.1"
PORT = 4173


def read_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"updatedAt": None, "geometries": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"updatedAt": None, "geometries": []}


def write_data(payload: dict[str, Any]) -> None:
    DATA_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_index(self) -> None:
        if not INDEX_FILE.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "index.html not found")
            return
        body = INDEX_FILE.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_index()
            return
        if path == "/api/overlays":
            self._send_json(read_data())
            return
        if path == "/overlays.json" and DATA_FILE.exists():
            body = DATA_FILE.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/overlays":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        geometries = payload.get("geometries")
        if not isinstance(geometries, list):
            self.send_error(HTTPStatus.BAD_REQUEST, "geometries must be a list")
            return

        data = {
            "updatedAt": payload.get("updatedAt"),
            "geometries": geometries,
        }
        write_data(data)
        self._send_json({"ok": True, "count": len(geometries)})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        # Keep server output minimal in the terminal.
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
