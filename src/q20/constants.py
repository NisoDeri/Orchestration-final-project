"""Immutable game constants: roles, outcomes, and default scoring.

All numbers here are *fallbacks* only — the live values come from
``config/setup.json:game.scoring`` (rubric: zero hardcoding). They exist so the
pure engine and its unit tests have a defined default when no config is supplied.
"""

from enum import StrEnum


class Role(StrEnum):
    """The two agents in a match."""

    JUDGE = "judge"
    PLAYER = "player"

    def other(self) -> "Role":
        return Role.PLAYER if self is Role.JUDGE else Role.JUDGE


class Outcome(StrEnum):
    """The player's result against the judge in one round."""

    WIN = "win"
    TIE = "tie"
    LOSS = "loss"


# Default per-round scoring (player points by outcome; judge a flat bonus).
# Mirrors config/setup.json:game.scoring so engine + tests have a fallback.
SCORE: dict[str, int] = {
    Outcome.WIN: 3,
    Outcome.TIE: 1,
    Outcome.LOSS: 1,
    "judge": 2,
}
