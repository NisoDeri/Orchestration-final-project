"""Small deterministic engine used by local tests and future network adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Action, GameState, MoveResult, Player
from .rules import apply_action


@dataclass
class GameEngine:
    state: GameState = field(default_factory=GameState)
    active_player: Player = Player.NORTH

    def play(self, action: Action) -> MoveResult:
        result = apply_action(self.state, self.active_player, action)
        self.state = result.state
        self.active_player = Player.SOUTH if self.active_player is Player.NORTH else Player.NORTH
        return result
