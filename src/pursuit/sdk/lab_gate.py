"""SDK gateway into the simulation lab (D7) — keeps the Table-5 gate airtight.

The CLI never imports :mod:`pursuit.lab` or :mod:`pursuit.strategy` directly; the
``lab`` subcommand routes through :func:`run_lab` here, so the SDK remains the single
entry for every way to play. Brains are selected by ``'module:Class'`` (the same
``[strategy]`` selector grammar as game.toml) and adapted onto the lab's view seam;
terms come from the signed game.json of ``config_dir`` — zero hardcoded parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pursuit.constants import DIRECTION_DELTAS, MoveType, Role
from pursuit.lab.arena import LabDecision
from pursuit.lab.runner import run_match
from pursuit.lab.stats import a_beats_b_p_value, points_per_scoring_table, win_rate
from pursuit.sdk.series import ScentBelief
from pursuit.shared.config import ConfigManager
from pursuit.strategy.resolve import load_brain_cls
from pursuit.strategy.talk import TemplateTalk

_TERMS_BLOCKS = ("board_and_agents", "movement_and_barriers", "scoring", "pheromones")


class _LabBrain:
    """Adapt a BrainBase brain onto the lab's view seam (LabView -> LabDecision)."""

    def __init__(self, brain: Any, barriers_max: int) -> None:
        self.brain, self.barriers_max = brain, int(barriers_max)

    def decide(self, view: Any) -> LabDecision:
        decision = self.brain.decide(view.state, view.belief, view.opponent_hint or "",
                                     "", self.barriers_max, None)
        if decision.move_type is MoveType.BARRIER:
            delta = DIRECTION_DELTAS[decision.direction]
            position = view.state.position
            return LabDecision(MoveType.BARRIER, hint=decision.hint,
                               barrier_cell=(position[0] + delta[0], position[1] + delta[1]))
        return LabDecision(decision.move_type, direction=decision.direction,
                           hint=decision.hint)


def _belief_factory(role: Role, terms: dict[str, Any]) -> ScentBelief:
    agents = terms["board_and_agents"]
    start = agents["thief_start"] if role is Role.POLICE else agents["cop_start"]
    return ScentBelief(tuple(start))


def run_lab(games: int, seed: int, police: str, thief: str,
            config_dir: str | Path) -> dict[str, Any]:
    """Paired-seed self-play match: ``games`` seeds x both role assignments (§6.3).

    ``police``/``thief`` are ``'module:Class'`` BrainBase selectors; agent A plays the
    named class for whichever role it draws, so the promotion stats stay role-balanced.
    """
    config = ConfigManager.load(config_dir)
    config.validate_agreement()
    terms = {block: config.game(block) for block in _TERMS_BLOCKS}
    classes = {Role.POLICE: load_brain_cls(police), Role.THIEF: load_brain_cls(thief)}
    setting = str(config.game("world.map_area"))
    hint_cap = int(config.game("world.hint_max_words"))
    barriers_max = int(terms["movement_and_barriers"]["max_barriers"])

    def spec(role: Role, rng: Any, _terms: dict) -> _LabBrain:
        talk = TemplateTalk(rng, setting, hint_cap)
        return _LabBrain(classes[Role(role)](talk, rng), barriers_max)

    rows = run_match(spec, spec, int(games), int(seed), terms,
                     belief_factory=_belief_factory)
    return {"games": len(rows), "win_rate_A": win_rate(rows),
            "p_value_A": a_beats_b_p_value(rows),
            "points": points_per_scoring_table(rows, terms["scoring"])}
