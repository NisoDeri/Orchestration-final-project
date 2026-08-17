"""Deliberately non-informative strategy for uncounted friendly games.

This policy ignores the belief map and opponent hints, chooses from the current
legal action set with injected randomness, and emits generic hints. It is for
protocol rehearsals only; it must never be used for a counted series.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, MoveType, Role
from pursuit.domain.rules import barrier_options
from pursuit.strategy.base import BeliefLike, BrainBase, Decision, TalkLike


class DummyTalk:
    """Generic filler talk that contains no coordinates or tactical claims."""

    _LINES = (
        "I am taking another route through the city.",
        "The streets are busy tonight.",
        "Still moving and checking the surroundings.",
        "Nothing useful to report yet.",
    )

    def __init__(self, rng: Any) -> None:
        self.rng = rng

    def say(self, role: Role, state: Any, belief: Any, setting: str,
            opponent_hint: str, deadline: float | None) -> tuple[str, str, str, str]:
        return self.rng.choice(self._LINES), "truth", "friendly dummy talk", ""


class _FriendlyDummyBrain(BrainBase):
    """Shared random legal-action policy; never reads belief or opponent_hint."""

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        self._random_move = True
        return self.rng.choice(moves)


class FriendlyDummyThiefBrain(_FriendlyDummyBrain):
    role = Role.THIEF


class FriendlyDummyPoliceBrain(_FriendlyDummyBrain):
    role = Role.POLICE

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        options = barrier_options(state.board, state.position, state.barriers)
        if state.my_barriers < barriers_max and options and self.rng.random() < 0.2:
            target = self.rng.choice(options)
            delta = (target[0] - state.position[0], target[1] - state.position[1])
            direction = {
                (0, 0): Direction.STAY,
                (-1, 0): Direction.N,
                (1, 0): Direction.S,
                (0, -1): Direction.W,
                (0, 1): Direction.E,
            }[delta]
            self._random_move = True
            return MoveType.BARRIER, direction
        return super()._decide_move(state, belief, barriers_max)
