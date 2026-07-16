"""Live hint fusion pipeline: parse the opponent's words, fuse into belief, update the ledger."""

from __future__ import annotations

from pursuit.domain.belief.reliability import ReliabilityLedger
from pursuit.peer.hint_fusion import HintFuser, parse_claim

MOVE_SET = ["N", "S", "E", "W", "STAY"]
_LEDGER_CFG = {"hint_alpha0": 1.0, "hint_beta0": 1.0, "reliability_forget": 0.95,
               "injection_penalty": 0.25}


class _StubBelief:
    """Records fuse_hint calls and returns a fixed consistency (a real BeliefV2 surface)."""

    def __init__(self, consistency: float | None) -> None:
        self.consistency = consistency
        self.calls: list[tuple[dict, float]] = []

    def fuse_hint(self, claim: dict, reliability: float) -> float | None:
        self.calls.append((claim, reliability))
        return self.consistency


def test_parse_claim_reads_a_direction() -> None:
    assert parse_claim("I'm heading north past the park", MOVE_SET)["claimed_direction"] == "N"
    assert parse_claim("bare W letter", MOVE_SET)["claimed_direction"] == "W"


def test_parse_claim_none_without_a_direction() -> None:
    assert parse_claim("just wandering the streets", MOVE_SET) is None
    assert parse_claim("", MOVE_SET) is None


def test_fuser_fuses_then_updates_ledger() -> None:
    ledger = ReliabilityLedger(dict(_LEDGER_CFG))
    belief = _StubBelief(0.9)
    r0 = ledger.value()
    HintFuser(ledger, MOVE_SET).fuse(belief, "moving east now")
    assert belief.calls and belief.calls[0][0]["claimed_direction"] == "E"
    assert belief.calls[0][1] == r0  # fused at the pre-update reliability
    assert ledger.value() != r0  # consistency folded back in


def test_fuser_no_direction_does_not_fuse() -> None:
    belief = _StubBelief(0.9)
    HintFuser(ReliabilityLedger(dict(_LEDGER_CFG)), MOVE_SET).fuse(belief, "hello")
    assert belief.calls == []


def test_fuser_noop_on_standin_belief_without_fuse_hint() -> None:
    class _Plain:
        pass

    HintFuser(ReliabilityLedger(dict(_LEDGER_CFG)), MOVE_SET).fuse(_Plain(), "go north")  # no crash


def test_fuser_none_consistency_leaves_ledger_unchanged() -> None:
    ledger = ReliabilityLedger(dict(_LEDGER_CFG))
    r0 = ledger.value()
    HintFuser(ledger, MOVE_SET).fuse(_StubBelief(None), "south bound")
    assert ledger.value() == r0
