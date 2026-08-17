"""Persist inbound submit_audit payloads from ngrok's local inspection API.

The game processes remain untouched. Each unique request is appended as one JSON line so
late report reconciliation and opponent-policy analysis retain the full revealed records.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


def _requests(api_url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(api_url, timeout=3) as response:
        data = json.load(response)
    return list(data.get("requests", []))


def _audit(request: dict[str, Any]) -> dict[str, Any] | None:
    try:
        raw = base64.b64decode(request["request"]["raw"]).decode("utf-8")
        body = raw.split("\r\n\r\n", 1)[1]
        rpc = json.loads(body)
        if rpc.get("params", {}).get("name") != "submit_audit":
            return None
        return {
            "request_id": request["id"],
            "received_at": request.get("start"),
            "uri": request.get("request", {}).get("uri"),
            "payload": rpc["params"]["arguments"]["payload"],
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            found.add(str(json.loads(line)["request_id"]))
        except (KeyError, TypeError, ValueError):
            pass
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--api", default="http://127.0.0.1:4040/api/requests/http?limit=100")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen = _seen(args.output)
    while True:
        try:
            rows = sorted(_requests(args.api), key=lambda row: str(row.get("start", "")))
            with args.output.open("a", encoding="utf-8") as stream:
                for request in rows:
                    item = _audit(request)
                    if item is None or item["request_id"] in seen:
                        continue
                    stream.write(json.dumps(item, ensure_ascii=False) + "\n")
                    stream.flush()
                    seen.add(item["request_id"])
        except OSError:
            pass
        time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    main()
