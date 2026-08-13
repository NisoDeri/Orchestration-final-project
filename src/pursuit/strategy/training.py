"""Friendly-only non-revealing baseline brains.

These policies are intentionally simple, stochastic, and legal. They are for compatibility
smoke tests and non-counted demos where we do not want to expose tuned league behavior.
They are not throw policies: every move is legal and the normal audit/report path remains honest.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, MoveType, Role
from pursuit.strategy.base import BeliefLike, BrainBase, TalkLike


class FriendlyMaskingThiefBrain(BrainBase):
    """Random-walk thief baseline for friendly demos."""

    role = Role.THIEF

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        self._random_move = True
        return self.rng.choice(moves)


class FriendlyMaskingPoliceBrain(BrainBase):
    """Random-walk police baseline with occasional random legal barriers."""

    role = Role.POLICE

    def __init__(
        self, talk: TalkLike, rng: Any, *, barrier_coin_p: float = 0.2
    ) -> None:
        super().__init__(talk, rng)
        self.barrier_coin_p = float(barrier_coin_p)

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return (MoveType.HOLD, None)
        barrier_moves = [(direction, cell) for direction, cell in moves if cell != state.position]
        if (
            barrier_moves
            and state.my_barriers < barriers_max
            and self.rng.random() < self.barrier_coin_p
        ):
            self._random_move = True
            direction, _cell = self.rng.choice(barrier_moves)
            return (MoveType.BARRIER, direction)
        self._random_move = True
        direction, _cell = self.rng.choice(moves)
        return (MoveType.MOVE, direction)

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        self._random_move = True
        return self.rng.choice(moves)
