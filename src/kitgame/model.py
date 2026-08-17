"""Game-specific data types for Beacon Hunt.

The wire layer remains owned by ``pursuit``.  This module contains only the
new game's rules and state, which keeps the transport and audit code reusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Player(StrEnum):
    NORTH = "north"
    SOUTH = "south"


class Action(StrEnum):
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"
    STAY = "STAY"
    SCAN = "SCAN"
    CLAIM = "CLAIM"


Position = tuple[int, int]


@dataclass(frozen=True)
class GameState:
    """Publicly reproducible state needed to replay one player's actions."""

    board_size: int = 7
    turn: int = 0
    positions: dict[Player, Position] = field(
        default_factory=lambda: {Player.NORTH: (0, 0), Player.SOUTH: (6, 6)}
    )
    beacons: frozenset[Position] = frozenset({(3, 3), (1, 5), (5, 1)})
    claimed: dict[Player, frozenset[Position]] = field(
        default_factory=lambda: {Player.NORTH: frozenset(), Player.SOUTH: frozenset()}
    )

    def position(self, player: Player) -> Position:
        return self.positions[player]

    def score(self, player: Player) -> int:
        return len(self.claimed[player])


@dataclass(frozen=True)
class MoveResult:
    state: GameState
    action: Action
    player: Player
    position: Position
    claimed_beacon: Position | None = None
    finished: bool = False
