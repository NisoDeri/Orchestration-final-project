"""Path router for exposing both fixed-role MCP peers through one static ngrok domain."""

from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit


ROUTES: dict[str, tuple[str, int]] = {}
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _target(path: str) -> tuple[str, int, str] | None:
    split = urlsplit(path)
    for prefix, (host, port) in ROUTES.items():
        if split.path == prefix or split.path.startswith(prefix + "/"):
            stripped = split.path[len(prefix):] or "/"
            return host, port, urlunsplit(("", "", stripped, split.query, ""))
    return None


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _write_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._write_text(200, "MCP path proxy: use /cop/mcp or /thief/mcp\n")
            return
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        """Forward MCP streamable-HTTP session termination requests."""
        self._proxy()

    def do_HEAD(self) -> None:  # noqa: N802
        """Forward endpoint health probes instead of returning BaseHTTP 501."""
        self._proxy()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._proxy()

    def _proxy(self) -> None:
        target = _target(self.path)
        if target is None:
            self._write_text(404, "Unknown route. Use /cop/mcp or /thief/mcp\n")
            return
        host, port, path = target
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length) if length else None
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS and key.lower() != "host"
        }
        headers["host"] = f"{host}:{port}"
        conn = http.client.HTTPConnection(host, port, timeout=900)
        try:
            conn.request(self.command, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status, resp.reason)
            for key, value in resp.getheaders():
                if key.lower() not in HOP_HEADERS and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()
        except OSError as exc:
            self._write_text(502, f"Backend unavailable at {host}:{port}: {exc}\n")
        finally:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--cop-port", type=int, default=8802)
    parser.add_argument("--thief-port", type=int, default=8801)
    args = parser.parse_args()
    ROUTES.update({
        "/cop": (args.host, args.cop_port),
        "/thief": (args.host, args.thief_port),
    })
    server = ThreadingHTTPServer((args.host, args.port), Proxy)
    print(
        f"MCP path proxy listening on http://{args.host}:{args.port} "
        f"(/cop -> {args.cop_port}, /thief -> {args.thief_port})"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
