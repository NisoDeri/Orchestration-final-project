"""CenterThief survives a catching cop where SurvivorThief is caught (loss-mined upgrade)."""

from __future__ import annotations

from pursuit.constants import Role
from pursuit.lab.runner import _play_one
from pursuit.sdk.lab_gate import _belief_or_scent, _load, _spec_for
from pursuit.strategy.resolve import load_brain_cls

COP = load_brain_cls("pursuit.strategy.police:InterceptorPoliceBrain")


def _survival_rate(thief_selector: str, games: int = 8) -> float:
    terms, setting, cap, bmax = _load("config/police")
    thief = load_brain_cls(thief_selector)
    specs = {r: _spec_for({Role.POLICE: COP, Role.THIEF: thief}, setting, cap, bmax)
             for r in ("A", "B")}
    survived = sum(1 for i in range(games)
                   if _play_one(i, 2000 + i, "A", specs, terms, _belief_or_scent)["result"]
                   == "survival")
    return survived / games


def test_center_thief_beats_baseline_vs_catching_cop():
    baseline = _survival_rate("pursuit.strategy.thief:SurvivorThiefBrain")
    center = _survival_rate("pursuit.strategy.center_thief:CenterThief")
    assert baseline == 0.0, f"expected baseline caught 100%, got survival {baseline}"
    assert center >= 0.9, f"CenterThief should survive the catching cop, got {center}"


def test_center_thief_is_the_default_thief():
    from pursuit.strategy.center_thief import CenterThief
    from pursuit.strategy.resolve import _DEFAULT_BRAINS
    assert _DEFAULT_BRAINS[Role.THIEF] is CenterThief
