"""Smoke-import tests for GUI modules: they must not crash on import even headless.

The GUI modules (board_view, window, replay_view, live_game) only call tk.Tk()
when their run() / mainloop() methods are invoked, so a bare import is always safe.
"""

from __future__ import annotations

import importlib
import sys


def _skip_if_no_tkinter():
    """Return a pytest.skip string if tkinter is unavailable (rare but possible)."""
    import pytest

    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        pytest.skip("tkinter not available in this environment")


def test_board_view_importable():
    _skip_if_no_tkinter()
    mod = importlib.import_module("pursuit.interface.board_view")
    assert hasattr(mod, "BoardView")
    assert hasattr(mod, "CELL_PX")
    assert hasattr(mod, "ROLE_COLORS")


def test_window_importable():
    _skip_if_no_tkinter()
    mod = importlib.import_module("pursuit.interface.window")
    assert hasattr(mod, "PeerWindow")


def test_live_game_importable():
    # live_game only imports threading/queue at module level — no tkinter
    mod = importlib.import_module("pursuit.interface.live_game")
    assert hasattr(mod, "LiveGameDriver")
    assert hasattr(mod, "start_game_thread")


def test_replay_view_importable():
    _skip_if_no_tkinter()
    mod = importlib.import_module("pursuit.interface.replay_view")
    assert hasattr(mod, "ReplayViewer")


def test_interface_package_importable():
    mod = importlib.import_module("pursuit.interface")
    assert mod is not None


def test_replay_viewer_no_mainloop_on_init(tmp_path):
    """ReplayViewer.__init__ must not call mainloop or open a window."""
    _skip_if_no_tkinter()
    import json

    from pursuit.interface.replay_view import ReplayViewer

    # Build a minimal valid log file
    log_file = tmp_path / "test.json"
    records = [
        {
            "commit": "aabbcc",
            "payload": {
                "role": "police",
                "board_size": 4,
                "position": [0, 0],
                "barriers": [],
                "message": None,
            },
        }
    ]
    log_file.write_text(json.dumps(records), encoding="utf-8")

    # Should construct without raising even though commit does not match
    viewer = ReplayViewer(log_file)
    assert isinstance(viewer._records, list)
    assert len(viewer._records) == 1
    # verified flag should be False (fake commit hash)
    assert viewer._verified is False
