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


def test_move_string_spelling_is_tolerated() -> None:
    # kit rule: judge the TRAIL, not the move-string. A one-step move whose label disagrees
    # with the delta (or a blocked-move sealed against its attempted direction) is NOT tampering.
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(2, [3, 3], "MOVE:N")]  # went S, labelled N
    assert trajectory_mismatches(records, BOARD) == []


def test_position_less_schema_is_skipped_not_accused() -> None:
    # a legitimate action+state-only schema (one real league team seals no position)
    records = [SimpleNamespace(payload={"step": 1, "move": "MOVE:N"}),
               SimpleNamespace(payload={"step": 2, "move": "MOVE:E"})]
    assert trajectory_mismatches(records, BOARD) == []


def test_out_of_bounds_and_malformed_never_crash() -> None:
    records = [_rec(1, [9, 9], "MOVE:N"), _rec(2, [0, 0], "NONSENSE"),
               SimpleNamespace(payload={"step": 3})]
    assert 1 in trajectory_mismatches(records, BOARD)  # off-board flagged; no crash


def test_skipped_step_number_is_tolerated() -> None:
    # step numbering is the binding layer's concern; physics only judges the trail (<=1 step)
    records = [_rec(1, [2, 3], "MOVE:N"), _rec(3, [2, 4], "MOVE:E")]  # step 2 "missing"
    assert trajectory_mismatches(records, BOARD) == []
