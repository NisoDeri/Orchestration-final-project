"""Semantic replay audit — re-simulate the opponent's REVEALED trajectory for legality.

Commit-reveal + live-commit binding prove the opponent did not CHANGE its sealed log after
seeing our moves; this proves the sealed log is a LEGAL game. Each revealed position is
post-move (turn_sender seals AFTER applying), so a legal chain satisfies:

  position[t] == position[t-1] + delta(move[t])     (MOVE:D advances by D; HOLD/BARRIER hold)

plus in-bounds cells and consecutive step numbers. A teleport, a through-the-grid jump, a
move-string that disagrees with the position it sealed, or a skipped step is provable
forgery — the caller folds these into ``failed_steps`` → ``technical_loss`` 0/0 (A9a).

Uses only the opponent's own revealed records + the board geometry (no second log needed),
so it runs on either peer independently and reaches the same verdict.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import DIRECTION_DELTAS, MoveType
from pursuit.domain.protocol_audit import parse_move_string
from pursuit.exceptions import TransportError


def _payload(record: Any) -> dict[str, Any]:
    """The record's payload dict whether it is an AuditRecord or a raw wire dict."""
    payload = getattr(record, "payload", None)
    if payload is None and isinstance(record, dict):
        payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def _cell(value: Any) -> tuple[int, int] | None:
    if (isinstance(value, list | tuple) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return (value[0], value[1])
    return None


def trajectory_mismatches(records: Any, board: Any) -> list[int]:
    """Steps whose revealed move-string is inconsistent with the revealed position path.

    Total over adversarial input: a malformed record fails its step, never crashes.
    """
    bad: list[int] = []
    prev: tuple[int, int] | None = None
    expected_step = 1
    for record in records:
        payload = _payload(record)
        step = payload.get("step")
        if step == 0:  # the step-0 signed declaration carries no move/position
            continue
        marker = step if isinstance(step, int) else expected_step
        pos = _cell(payload.get("position"))
        try:
            move_type, direction = parse_move_string(payload.get("move"))
        except TransportError:
            bad.append(marker)
            prev, expected_step = pos, expected_step + 1
            continue
        if pos is None or not board.in_bounds(pos):
            bad.append(marker)
        elif step != expected_step:
            bad.append(marker)  # a gap/duplicate in the sealed chain
        elif prev is not None:
            moved = move_type is MoveType.MOVE and direction is not None
            dr, dc = DIRECTION_DELTAS[direction] if moved else (0, 0)
            if pos != (prev[0] + dr, prev[1] + dc):  # teleport / move!=position delta
                bad.append(marker)
        prev = pos if pos is not None else prev
        expected_step += 1
    return sorted(set(bad))
