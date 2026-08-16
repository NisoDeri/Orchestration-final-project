"""AdaptivePoliceBrain catches a centre-player (0%->100%) with no regression on fleers."""

from __future__ import annotations

from pursuit.constants import Role
from pursuit.lab.runner import _play_one
from pursuit.sdk.lab_gate import _belief_or_scent, _load, _spec_for
from pursuit.strategy.resolve import load_brain_cls


def _capture_rate(cop_selector: str, thief_selector: str, games: int = 8) -> float:
    terms, setting, cap, bmax = _load("config/police")
    cop = load_brain_cls(cop_selector)
    thief = load_brain_cls(thief_selector)
    specs = {r: _spec_for({Role.POLICE: cop, Role.THIEF: thief}, setting, cap, bmax)
             for r in ("A", "B")}
    caught = sum(1 for i in range(games)
                 if _play_one(i, 5100 + i, "A", specs, terms, _belief_or_scent)["result"]
                 == "capture")
    return caught / games


ADAPTIVE = "pursuit.strategy.adaptive_police:AdaptivePoliceBrain"
BASE_COP = "pursuit.strategy.police:InterceptorPoliceBrain"
CENTER = "pursuit.strategy.center_thief:CenterThief"
SURVIVOR = "pursuit.strategy.thief:SurvivorThiefBrain"


def test_adaptive_cop_cages_center_player():
    assert _capture_rate(BASE_COP, CENTER) == 0.0       # baseline can't catch a centre-player
    assert _capture_rate(ADAPTIVE, CENTER) >= 0.9        # the cage counter does


def test_adaptive_cop_no_regression_on_fleer():
    assert _capture_rate(ADAPTIVE, SURVIVOR) >= 0.9      # still catches distance-fleers


def test_adaptive_is_the_default_cop():
    from pursuit.strategy.adaptive_police import AdaptivePoliceBrain
    from pursuit.strategy.resolve import _DEFAULT_BRAINS
    assert _DEFAULT_BRAINS[Role.POLICE] is AdaptivePoliceBrain
