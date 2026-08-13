"""Unit tests for resolve_brain / load_brain_cls — the [strategy] extension point."""

from __future__ import annotations

import random
from typing import Any

import pytest

from pursuit.constants import Role
from pursuit.exceptions import ConfigError
from pursuit.shared.config import ConfigManager
from pursuit.strategy.greedy import GreedyPoliceBrain
from pursuit.strategy.police import InterceptorPoliceBrain
from pursuit.strategy.resolve import load_brain_cls, resolve_brain
from pursuit.strategy.talk import TemplateTalk
from pursuit.strategy.thief import SurvivorThiefBrain
from pursuit.strategy.training import FriendlyMaskingPoliceBrain, FriendlyMaskingThiefBrain

GREEDY_POLICE = "pursuit.strategy.greedy:GreedyPoliceBrain"
FRIENDLY_POLICE = "pursuit.strategy.training:FriendlyMaskingPoliceBrain"
FRIENDLY_THIEF = "pursuit.strategy.training:FriendlyMaskingThiefBrain"


def make_config(private: dict[str, Any] | None = None,
                game: dict[str, Any] | None = None) -> ConfigManager:
    """In-memory ConfigManager — unit tests never touch the filesystem."""
    return ConfigManager(game_terms=game or {}, private_terms=private or {}, rate_limits={})


class SentinelTalk:
    def say(self, role, state, belief, setting, opponent_hint, deadline):
        return ("quiet night", "truth", "sentinel", "")


# --- load_brain_cls ---------------------------------------------------------------------------
def test_load_brain_cls_happy_path() -> None:
    assert load_brain_cls(GREEDY_POLICE) is GreedyPoliceBrain


@pytest.mark.parametrize(
    "selector",
    ["garbage", "pursuit.strategy.greedy", ":", "module:", ":Class",
     "definitely.not.a.module:Brain", "pursuit.strategy.greedy:NoSuchBrain",
     "pursuit.constants:Role", 123, None],
)
def test_load_brain_cls_rejects_malformed_selectors(selector: Any) -> None:
    with pytest.raises(ConfigError):
        load_brain_cls(selector)


# --- resolve_brain: defaults ------------------------------------------------------------------
def test_resolve_defaults_to_our_brains_per_role() -> None:
    rng = random.Random(0)
    cop = resolve_brain(make_config(), Role.POLICE, rng)
    thief = resolve_brain(make_config(), Role.THIEF, rng)
    assert isinstance(cop, InterceptorPoliceBrain)
    assert isinstance(thief, SurvivorThiefBrain)
    assert cop.rng is rng and thief.rng is rng  # injected, never self-seeded (STRATEGY §8.8)


def test_resolve_accepts_wire_role_string() -> None:
    brain = resolve_brain(make_config(), "police", random.Random(0))
    assert isinstance(brain, InterceptorPoliceBrain)


def test_resolve_builds_template_talk_with_interop_fallbacks() -> None:
    brain = resolve_brain(make_config(), Role.THIEF, random.Random(0))
    assert isinstance(brain.talk, TemplateTalk)
    assert brain.talk.setting == ""  # INTEROP §2.1 protocol-pinned defaults
    assert brain.talk.hint_max_words == 15


def test_resolve_reads_world_terms_from_game_json() -> None:
    game = {"world": {"setting": "London", "hint_max_words": 9}}
    brain = resolve_brain(make_config(game=game), Role.POLICE, random.Random(0))
    assert (brain.talk.setting, brain.talk.hint_max_words) == ("London", 9)


def test_resolve_accepts_map_area_as_setting() -> None:
    brain = resolve_brain(make_config(game={"world": {"map_area": "Haifa"}}),
                          Role.POLICE, random.Random(0))
    assert brain.talk.setting == "Haifa"


def test_resolve_accepts_arena_alias_for_setting() -> None:
    brain = resolve_brain(make_config(game={"world": {"arena": "Paris"}}),
                          Role.POLICE, random.Random(0))
    assert brain.talk.setting == "Paris"


def test_resolve_honors_injected_talk() -> None:
    sentinel = SentinelTalk()
    brain = resolve_brain(make_config(), Role.POLICE, random.Random(0), talk=sentinel)
    assert brain.talk is sentinel


# --- resolve_brain: [strategy] selectors ------------------------------------------------------
def test_resolve_loads_brain_by_dotted_path() -> None:
    config = make_config(private={"strategy": {"police_class": GREEDY_POLICE}})
    brain = resolve_brain(config, Role.POLICE, random.Random(0))
    assert isinstance(brain, GreedyPoliceBrain)


def test_resolve_selector_only_affects_its_role() -> None:
    config = make_config(private={"strategy": {"police_class": GREEDY_POLICE}})
    assert isinstance(resolve_brain(config, Role.THIEF, random.Random(0)), SurvivorThiefBrain)


def test_friendly_mode_uses_friendly_selector_when_present() -> None:
    config = make_config(private={
        "game": {"mode": "friendly"},
        "strategy": {
            "friendly_police_class": FRIENDLY_POLICE,
            "friendly_thief_class": FRIENDLY_THIEF,
            "police_class": "pursuit.strategy.police:InterceptorPoliceBrain",
            "thief_class": "pursuit.strategy.thief:SurvivorThiefBrain",
        },
    })
    assert isinstance(resolve_brain(config, Role.POLICE, random.Random(0)),
                      FriendlyMaskingPoliceBrain)
    assert isinstance(resolve_brain(config, Role.THIEF, random.Random(0)),
                      FriendlyMaskingThiefBrain)


def test_counted_mode_ignores_friendly_selector_and_uses_best_selector() -> None:
    config = make_config(private={
        "game": {"mode": "counted"},
        "strategy": {
            "friendly_police_class": FRIENDLY_POLICE,
            "police_class": "pursuit.strategy.police:InterceptorPoliceBrain",
        },
    })
    assert isinstance(resolve_brain(config, Role.POLICE, random.Random(0)),
                      InterceptorPoliceBrain)


@pytest.mark.parametrize(
    "selector", ["garbage-no-colon", "nosuch.module:Brain", "pursuit.constants:Role", 123]
)
def test_resolve_rejects_garbage_selectors(selector: Any) -> None:
    config = make_config(private={"strategy": {"thief_class": selector}})
    with pytest.raises(ConfigError):
        resolve_brain(config, Role.THIEF, random.Random(0))


# --- resolve_brain: private tuning tables -----------------------------------------------------
def test_resolve_passes_police_tuning_knobs() -> None:
    config = make_config(private={"police": {"barrier_finisher_p": 0.9, "cage_radius": 1,
                                             "unknown_knob": 5}})
    brain = resolve_brain(config, Role.POLICE, random.Random(0))
    assert isinstance(brain, InterceptorPoliceBrain)
    assert (brain.barrier_finisher_p, brain.cage_radius) == (0.9, 1)  # unknown_knob ignored


def test_resolve_passes_thief_tuning_knobs() -> None:
    config = make_config(private={"thief": {"w_dist": 2.0, "jail_min_mobility": 3}})
    brain = resolve_brain(config, Role.THIEF, random.Random(0))
    assert isinstance(brain, SurvivorThiefBrain)
    assert (brain.w_dist, brain.jail_min_mobility) == (2.0, 3)
    assert (brain.w_mob, brain.mobility_k) == (0.4, 3)  # untouched knobs keep their defaults


def test_resolve_rejects_non_table_tuning_block() -> None:
    with pytest.raises(ConfigError, match=r"\[thief\]"):
        resolve_brain(make_config(private={"thief": "fast"}), Role.THIEF, random.Random(0))


def test_resolve_custom_class_skips_our_tuning_tables() -> None:
    config = make_config(private={"strategy": {"police_class": GREEDY_POLICE},
                                  "police": {"barrier_finisher_p": 0.9}})
    brain = resolve_brain(config, Role.POLICE, random.Random(0))  # must not TypeError
    assert isinstance(brain, GreedyPoliceBrain)
