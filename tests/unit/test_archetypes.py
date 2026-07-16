"""The diverse lab opponents produce legal moves (they are stress-test brains, not league)."""

from __future__ import annotations

import random

from pursuit.constants import Cell, MoveType
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.strategy.archetypes import (
    CornerAmbushPolice,
    RandomPolice,
    RandomThief,
    WallHuggerThief,
)


class _Belief:
    def __init__(self, mode: Cell) -> None:
        self._mode = mode

    def most_likely(self) -> Cell:
        return self._mode

    def most_likely_p(self) -> float:
        return 1.0


class _Talk:
    def say(self, *a: object):  # noqa: ANN002
        return ("", "truth", "", "")


def _state(pos: Cell) -> OwnGameState:
    return OwnGameState(Board(7, ["N", "S", "E", "W", "STAY"]), pos)


def test_every_archetype_returns_a_legal_move() -> None:
    rng = random.Random(0)
    belief = _Belief((3, 3))
    for cls in (RandomThief, RandomPolice, WallHuggerThief, CornerAmbushPolice):
        brain = cls(_Talk(), rng)
        decision = brain.decide(_state((1, 1)), belief, "", "NY", 14)
        assert decision.move_type in (MoveType.MOVE, MoveType.HOLD)
        if decision.move_type is MoveType.MOVE:
            assert decision.direction is not None
