"""Pure routing tests for the unified MCP path proxy."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_proxy_module():
    path = Path(__file__).resolve().parents[2] / "tools" / "mcp_path_proxy.py"
    spec = importlib.util.spec_from_file_location("mcp_path_proxy_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_turn_sender_routes_to_opposite_local_role():
    proxy = _load_proxy_module()
    proxy.ROLE_ROUTES.update({"police": ("127.0.0.1", 8802), "thief": ("127.0.0.1", 8801)})

    assert proxy.role_for_tool_call("receive_turn", {"message": {"sender": "thief"}}) == "police"
    assert proxy.role_for_tool_call("receive_turn", {"message": {"sender": "police"}}) == "thief"


def test_audit_and_control_sender_route_to_opposite_local_role():
    proxy = _load_proxy_module()
    proxy.ROLE_ROUTES.update({"police": ("127.0.0.1", 8802), "thief": ("127.0.0.1", 8801)})

    assert proxy.role_for_tool_call("submit_audit", {"payload": {"sender": "police"}}) == "thief"
    assert proxy.role_for_tool_call("receive_control", {"message": {"sender": "thief"}}) == "police"


def test_negotiate_declared_role_routes_to_opposite_local_role():
    proxy = _load_proxy_module()
    proxy.ROLE_ROUTES.update({"police": ("127.0.0.1", 8802), "thief": ("127.0.0.1", 8801)})

    assert proxy.role_for_tool_call("negotiate", {"message": {"role": "thief"}}) == "police"
    assert proxy.role_for_tool_call("negotiate", {"message": {"role": "police"}}) == "thief"


def test_negotiate_subgame_fallback_uses_our_starting_role():
    proxy = _load_proxy_module()
    proxy.ROLE_ROUTES.update({"police": ("127.0.0.1", 8802), "thief": ("127.0.0.1", 8801)})
    proxy.MY_STARTING_ROLE = "police"

    assert proxy.role_for_tool_call("negotiate", {"message": {"sub_game_number": 1}}) == "police"
    assert proxy.role_for_tool_call("negotiate", {"message": {"sub_game_number": 2}}) == "thief"


def test_unroutable_call_returns_none():
    proxy = _load_proxy_module()
    proxy.ROLE_ROUTES.update({"police": ("127.0.0.1", 8802), "thief": ("127.0.0.1", 8801)})

    assert proxy.role_for_tool_call("receive_turn", {"message": {}}) is None
