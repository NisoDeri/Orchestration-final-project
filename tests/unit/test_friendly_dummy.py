from random import Random

from pursuit.constants import Direction, Role
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.strategy.friendly_dummy import (
    DummyTalk,
    FriendlyDummyPoliceBrain,
    FriendlyDummyThiefBrain,
)


class _Belief:
    def most_likely(self):
        raise AssertionError("friendly dummy must not inspect belief")

    def most_likely_p(self):
        raise AssertionError("friendly dummy must not inspect belief")


def _state(role: Role) -> OwnGameState:
    start = (0, 0) if role is Role.POLICE else (3, 3)
    return OwnGameState(Board(7, ["N", "S", "E", "W", "STAY"]), start)


def test_dummy_brains_ignore_belief_and_produce_legal_decisions() -> None:
    for role, cls in ((Role.POLICE, FriendlyDummyPoliceBrain),
                      (Role.THIEF, FriendlyDummyThiefBrain)):
        brain = cls(DummyTalk(Random(4)), Random(4))
        decision = brain.decide(_state(role), _Belief(), "predictable hint", "New York", 14)
        assert decision.random_move
        assert decision.direction in (Direction.N, Direction.S, Direction.E, Direction.W,
                                      Direction.STAY, None)


def test_dummy_talk_has_no_coordinates() -> None:
    hint, verdict, _, _ = DummyTalk(Random(1)).say(
        Role.THIEF, None, None, "New York", "", None
    )
    assert verdict == "truth"
    assert not any(char.isdigit() for char in hint)
