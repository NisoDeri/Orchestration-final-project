"""Router for exposing both fixed-role MCP peers through one public endpoint.

The historical routes ``/cop/mcp`` and ``/thief/mcp`` remain as pass-through aliases.
The unified ``/mcp`` route speaks the small streamable-HTTP MCP subset we need and
forwards each tool call to the local fixed-role backend that should receive it.
"""

from __future__ import annotations

import argparse
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit


ROUTES: dict[str, tuple[str, int]] = {}
ROLE_ROUTES: dict[str, tuple[str, int]] = {}
MY_STARTING_ROLE = "police"
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
TOOL_ARGUMENT_KEYS = {
    "negotiate": "message",
    "receive_turn": "message",
    "submit_audit": "payload",
    "receive_control": "message",
}
PROTOCOL_VERSION = "2025-06-18"
BASE_MCP_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}
TOOLS = (
    {"name": "negotiate", "inputSchema": {"type": "object"}},
    {"name": "receive_turn", "inputSchema": {"type": "object"}},
    {"name": "submit_audit", "inputSchema": {"type": "object"}},
    {"name": "receive_control", "inputSchema": {"type": "object"}},
)


def _target(path: str) -> tuple[str, int, str] | None:
    split = urlsplit(path)
    for prefix, (host, port) in ROUTES.items():
        if split.path == prefix or split.path.startswith(prefix + "/"):
            stripped = split.path[len(prefix):] or "/"
            return host, port, urlunsplit(("", "", stripped, split.query, ""))
    return None


def _opposite(role: str) -> str:
    if role == "thief":
        return "police"
    if role == "police":
        return "thief"
    raise ValueError(f"unknown role: {role!r}")


def _role_for_subgame(number: int) -> str:
    if number % 2 == 1:
        return MY_STARTING_ROLE
    return _opposite(MY_STARTING_ROLE)


def _message_body(tool: str, arguments: dict) -> dict | None:
    key = TOOL_ARGUMENT_KEYS.get(tool)
    if key is None:
        return None
    body = arguments.get(key)
    return body if isinstance(body, dict) else None


def role_for_tool_call(tool: str, arguments: dict) -> str | None:
    """Return our fixed-role backend for an incoming unified-endpoint tool call.

    Turn, audit and control messages identify the remote sender, so the receiver is our
    opposite role. Negotiation should carry the remote ``role`` too; if a peer omits it,
    fall back to the declared sub-game number and our configured starting role.
    """
    body = _message_body(tool, arguments)
    if body is None:
        return None
    sender = body.get("sender")
    if sender in ROLE_ROUTES:
        return _opposite(str(sender))
    if tool == "negotiate":
        role = body.get("role")
        if role in ROLE_ROUTES:
            return _opposite(str(role))
        number = body.get("sub_game_number")
        if isinstance(number, int) and not isinstance(number, bool):
            return _role_for_subgame(number)
    return None


def _rpc_messages(data: bytes, content_type: str) -> list[dict]:
    text = data.decode("utf-8")
    if "text/event-stream" in content_type:
        return [json.loads(line[5:].strip()) for line in text.splitlines()
                if line.startswith("data:")]
    return [json.loads(text)]


def _rpc_result(status: int, data: bytes, content_type: str, rpc_id: int) -> dict:
    if status >= 400:
        raise OSError(f"backend returned HTTP {status}")
    for message in _rpc_messages(data, content_type):
        if message.get("id") == rpc_id and "error" in message:
            raise OSError(f"backend MCP error: {message['error']}")
        if message.get("id") == rpc_id and "result" in message:
            return message["result"]
    raise OSError("backend MCP response did not contain a JSON-RPC result")


def _post_json(host: str, port: int, path: str, payload: dict,
               headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    conn = http.client.HTTPConnection(host, port, timeout=900)
    try:
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read()
        return response.status, data, {key.lower(): value for key, value in response.getheaders()}
    finally:
        conn.close()


def call_backend_tool(host: str, port: int, tool: str, arguments: dict) -> dict:
    headers = dict(BASE_MCP_HEADERS)
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": "pursuit-unified-proxy", "version": "0.1.0"}}}
    status, data, response_headers = _post_json(host, port, "/mcp", init, headers)
    _rpc_result(status, data, response_headers.get("content-type", ""), 1)
    if response_headers.get("mcp-session-id"):
        headers["mcp-session-id"] = response_headers["mcp-session-id"]
    _post_json(host, port, "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"},
               headers)
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": arguments}}
    status, data, response_headers = _post_json(host, port, "/mcp", call, headers)
    return _rpc_result(status, data, response_headers.get("content-type", ""), 2)


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

    def _write_json(self, status: int, payload: dict,
                    extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _is_unified_mcp(self) -> bool:
        return urlsplit(self.path).path.rstrip("/") == "/mcp"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._write_text(200, "MCP proxy: use /mcp (or /cop/mcp, /thief/mcp)\n")
            return
        if self._is_unified_mcp():
            self._write_text(200, "Unified MCP endpoint. Use POST streamable HTTP.\n")
            return
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        if self._is_unified_mcp():
            self._unified_mcp()
            return
        self._proxy()

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._is_unified_mcp():
            self.send_response(204)
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("access-control-allow-headers", "content-type, mcp-session-id")
            self.send_header("content-length", "0")
            self.end_headers()
            return
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        if self._is_unified_mcp():
            self.send_response(202)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        self._proxy()

    def _unified_mcp(self) -> None:
        length = int(self.headers.get("content-length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            message = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            self._write_json(400, _mcp_error(None, -32700, f"invalid JSON: {exc}"))
            return
        rpc_id = message.get("id")
        method = message.get("method")
        if method == "initialize":
            self._write_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "pursuit-unified-proxy", "version": "0.1.0"},
                },
            }, {"mcp-session-id": "pursuit-unified-proxy"})
            return
        if method == "notifications/initialized":
            self.send_response(202)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        if method == "tools/list":
            self._write_json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": list(TOOLS)}})
            return
        if method != "tools/call":
            self._write_json(400, _mcp_error(rpc_id, -32601, f"unknown MCP method: {method!r}"))
            return
        params = message.get("params")
        params = params if isinstance(params, dict) else {}
        tool = params.get("name")
        arguments = params.get("arguments")
        arguments = arguments if isinstance(arguments, dict) else {}
        role = role_for_tool_call(str(tool), arguments)
        if role is None:
            self._write_json(400, _mcp_error(
                rpc_id, -32602, f"cannot route tool call {tool!r}; role/sender missing"))
            return
        host, port = ROLE_ROUTES[role]
        try:
            result = call_backend_tool(host, port, str(tool), arguments)
        except OSError as exc:
            self._write_json(502, _mcp_error(
                rpc_id, -32000, f"backend unavailable for {role} at {host}:{port}: {exc}"))
            return
        self._write_json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": result})

    def _proxy(self) -> None:
        target = _target(self.path)
        if target is None:
            self._write_text(404, "Unknown route. Use /mcp, /cop/mcp, or /thief/mcp\n")
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


def _mcp_error(rpc_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--cop-port", type=int, default=8802)
    parser.add_argument("--thief-port", type=int, default=8801)
    parser.add_argument("--my-starting-role", choices=("police", "thief"), default="police",
                        help="our role in odd sub-games, used only if negotiate omits role")
    args = parser.parse_args()
    ROUTES.update({
        "/cop": (args.host, args.cop_port),
        "/thief": (args.host, args.thief_port),
    })
    ROLE_ROUTES.update({
        "police": (args.host, args.cop_port),
        "thief": (args.host, args.thief_port),
    })
    global MY_STARTING_ROLE
    MY_STARTING_ROLE = args.my_starting_role
    server = ThreadingHTTPServer((args.host, args.port), Proxy)
    print(
        f"MCP path proxy listening on http://{args.host}:{args.port} "
        f"(/mcp unified, /cop -> {args.cop_port}, /thief -> {args.thief_port}; "
        f"odd sub-games -> {MY_STARTING_ROLE})"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
