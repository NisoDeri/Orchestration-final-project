"""Bridge Beacon Hunt turns to the existing kit-compatible wire envelopes.

The kit's public turn schema is intentionally preserved.  Beacon Hunt meaning
is carried in the sealed payload, so the opponent cannot learn a position or
action before the audit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pursuit.domain.protocol import TurnMessage
from pursuit.peer.sealing import SealedLog

from .model import Action, GameState, Player

_WIRE_ROLE = {Player.NORTH: "police", Player.SOUTH: "thief"}


def seal_turn(
    log: SealedLog,
    player: Player,
    state: GameState,
    action: Action,
    step: int,
    hint: str = "I am searching for a beacon.",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(wire_message, local_record)`` for one Beacon Hunt action."""
    payload = {
        "step": step,
        "game": "beacon_hunt",
        "player": player.value,
        "position": list(state.position(player)),
        "action": action.value,
    }
    record = log.seal_step(payload)
    message = TurnMessage(
        step=step,
        sender=_WIRE_ROLE[player],
        hint=hint,
        smell_grid={},
        commit=record["commit"],
        timestamp=datetime.now(UTC).isoformat(),
    )
    return message.to_wire(), record
