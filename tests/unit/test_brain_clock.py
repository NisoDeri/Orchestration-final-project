"""Bounded brain execution: a slow/hung brain degrades to a safe HOLD, never a freeze."""

from __future__ import annotations

import time

from pursuit.constants import MoveType
from pursuit.peer.brain_clock import decide_bounded
from pursuit.strategy.base import Decision


class _FastBrain:
    def decide(self, *args: object) -> Decision:
        return Decision(MoveType.MOVE, None, "quick", "truth")


class _SlowBrain:
    def decide(self, *args: object) -> Decision:
        time.sleep(2.0)  # exceeds the tiny deadline below
        return Decision(MoveType.MOVE, None, "too late", "truth")


def test_fast_brain_returns_its_own_decision() -> None:
    decision = decide_bounded(_FastBrain(), (), deadline_seconds=1.0)
    assert decision.hint == "quick" and not decision.random_move


def test_slow_brain_degrades_to_safe_hold() -> None:
    decision = decide_bounded(_SlowBrain(), (), deadline_seconds=0.05)
    assert decision.move_type is MoveType.HOLD
    assert decision.random_move  # flagged in the sealed record


def test_none_deadline_runs_inline() -> None:
    decision = decide_bounded(_FastBrain(), (), deadline_seconds=None)
    assert decision.hint == "quick"
