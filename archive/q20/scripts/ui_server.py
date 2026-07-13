"""Serve the q20 web UI (league standings + single-round replay) and open it.

    uv run python scripts/ui_server.py            # serve + open the UI
    uv run python scripts/ui_server.py --port 9000 --no-open

Roots at the project dir so the page can fetch BOTH ``ui/`` assets and the live
``artifacts/league.json`` / ``artifacts/round_log.json`` written by the q20 CLI. Run a
match in another terminal (``q20 play-round --fake`` / ``q20 run-league``) then click
"Reload latest". A bundled ``ui/sample_round.json`` plays out of the box. No-cache so
edits to app.js/theme.css land on a plain refresh. Stdlib only; forces UTF-8 I/O.
"""

import argparse
import functools
import http.server
import os
import sys
import webbrowser
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):  # Hebrew path -> force UTF-8 even on cp1252 consoles
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
ROOT = Path(__file__).resolve().parents[1]


class _NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Serve with no-store so artifact/asset edits are picked up on a plain refresh."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:  # quieter console
        sys.stderr.write("  " + (fmt % args) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="serve the q20 league/replay UI")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="don't auto-open the browser")
    args = ap.parse_args()

    handler = functools.partial(_NoCacheHandler, directory=str(ROOT))
    url = f"http://127.0.0.1:{args.port}/ui/index.html"
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"serving {ROOT} at {url}\nCtrl+C to stop")  # noqa: T201
        if not args.no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")  # noqa: T201


if __name__ == "__main__":
    main()
