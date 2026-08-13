"""friendly/counted mode selector — one switch drives recipient + counted counters."""

from types import SimpleNamespace

from pursuit.peer.hint_fusion import build_hint_fuser
from pursuit.sdk.series_log import _game_mode, _mode_recipient


def _cfg(private: dict):
    return SimpleNamespace(
        private=lambda path: _dig(private, path),
        game=lambda path: _dig(private, path),
    )


def _dig(tree: dict, path: str):
    node = tree
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            from pursuit.exceptions import ConfigError
            raise ConfigError(f"missing {path}")
        node = node[part]
    return node


FRIENDLY = "a@x.com, b@y.com"
LECTURER = "lecturer@uni.edu"
EMAIL = {"email": {"recipient_friendly": FRIENDLY, "recipient_counted": LECTURER}}


def test_default_mode_is_friendly_safe():
    # absent game.mode -> friendly (a report can only reach the lecturer when EXPLICITLY counted)
    assert _game_mode(_cfg(EMAIL)) == "friendly"
    assert _mode_recipient(_cfg(EMAIL)) == FRIENDLY


def test_counted_mode_targets_lecturer():
    cfg = _cfg({"game": {"mode": "counted"}, **EMAIL})
    assert _game_mode(cfg) == "counted"
    assert _mode_recipient(cfg) == LECTURER


def test_friendly_mode_targets_both_inboxes():
    cfg = _cfg({"game": {"mode": "friendly"}, **EMAIL})
    assert _game_mode(cfg) == "friendly"
    assert _mode_recipient(cfg) == FRIENDLY


def test_unknown_mode_falls_back_to_friendly():
    cfg = _cfg({"game": {"mode": "nonsense"}, **EMAIL})
    assert _game_mode(cfg) == "friendly"  # never accidentally counted


def test_legacy_single_recipient_still_honored():
    cfg = _cfg({"email": {"recipient": "solo@x.com"}})
    assert _mode_recipient(cfg) == "solo@x.com"


def test_friendly_mode_disables_hint_fusion_learning():
    cfg = _cfg({
        "game": {"mode": "friendly"},
        "strategy": {"fuse_hints": True},
        "belief": {"hint_trust_prior": 0.5, "hint_prior_strength": 2.0,
                   "reliability_forget": 0.95},
        "llm_defense": {"injection_penalty": 0.25},
    })
    assert build_hint_fuser(cfg) is None


def test_counted_mode_can_enable_hint_fusion_learning():
    cfg = _cfg({
        "game": {"mode": "counted"},
        "strategy": {"fuse_hints": True},
        "belief": {"hint_trust_prior": 0.5, "hint_prior_strength": 2.0,
                   "reliability_forget": 0.95},
        "llm_defense": {"injection_penalty": 0.25},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"]},
    })
    assert build_hint_fuser(cfg) is not None
