"""Send one advisory receive_control message to a peer MCP endpoint.

Run from the repo root, for example:
    python tools/send_mcp_control.py --url https://example.com/mcp --file message.json

The file must contain the ControlMessage body itself, not the JSON-RPC wrapper:
    {"kind": "status", "sender": "police", "payload": {"note": "ready"}}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pursuit.domain.protocol import ControlMessage  # noqa: E402
from pursuit.infra.transport import http_call_tool  # noqa: E402


def _load_message(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"message file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None
    if not isinstance(data, dict):
        raise SystemExit("control message must be a JSON object")
    try:
        ControlMessage.from_wire(data)
    except Exception as exc:  # noqa: BLE001 - command-line validation should print the exact cause.
        raise SystemExit(f"invalid ControlMessage: {exc}") from None
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send an MCP receive_control message")
    parser.add_argument("--url", required=True, help="peer MCP endpoint, ending in /mcp")
    parser.add_argument("--file", required=True, type=Path, help="JSON ControlMessage file")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    message = _load_message(args.file)
    ack = http_call_tool(args.url, "receive_control", {"message": message}, args.timeout)
    print(json.dumps(ack, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
