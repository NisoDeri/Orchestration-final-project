"""Semantic replay audit: the opponent's REVEALED trajectory must be physically legal.

Beyond hash + live-commit binding, this proves the sealed positions form a real game —
each post-move position equals the previous plus the revealed move's delta, in-bounds,
step-consecutive. A teleport or a move-string that disagrees with its sealed position is
provable forgery (technical_loss 0/0).
"""

from __future__ import annotations

from types import SimpleNamespace

from pursuit.domain.board import Board
from pursuit.peer.replay_audit import trajectory_mismatches

MOVE_SET = ["N", "S", "E", "W", "STAY"]
BOARD = Board(7, MOVE_SET)


def _rec(step: int, position: list[int], move: str) -> SimpleNamespace:
    return SimpleNamespace(payload={"step": step, "position": position, "move": move})


def _decl() -> SimpleNamespace:
    return SimpleNamespace(payload={"step": 0, "type": "system_spec"})


def test_legal_trajectory_passes() -> None:
    # thief from [3,3]: N->[2,3], E->[2,4], HOLD->[2,4], S->[3,4]
    records = [_decl(), _rec(1, [2, 3], "MOVE:N"), _rec(2, [2, 4], "MOVE:E"),
               _rec(3, [2, 4], "HOLD:-"), _rec(4, [3, 4], "MOVE:S")]
    assert trajectory_mismatches(records, BOARD) == []


def test_teleport_is_caught() -> None:
    # step 2 claims MOVE:E from [2,3] but seals [5,5] — impossible jump
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(2, [5, 5], "MOVE:E")]
    assert trajectory_mismatches(records, BOARD) == [2]


def test_move_string_disagrees_with_position() -> None:
    # claims MOVE:N (up) but the sealed position went DOWN
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(2, [3, 3], "MOVE:N")]
    assert trajectory_mismatches(records, BOARD) == [2]


def test_hold_that_moved_is_caught() -> None:
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(2, [1, 3], "HOLD:-")]
    assert trajectory_mismatches(records, BOARD) == [2]


def test_out_of_bounds_and_malformed_never_crash() -> None:
    records = [_rec(1, [9, 9], "MOVE:N"), _rec(2, [0, 0], "NONSENSE"),
               SimpleNamespace(payload={"step": 3})]
    assert set(trajectory_mismatches(records, BOARD)) >= {1, 2, 3}


def test_skipped_step_is_caught() -> None:
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(3, [2, 4], "MOVE:E")]  # step 2 missing
    assert 3 in trajectory_mismatches(records, BOARD)
