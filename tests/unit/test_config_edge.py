"""Edge cases for config loading + version validation + the round-state carriers."""

import json

import pytest

from q20.game.corpus import Paragraph
from q20.game.round import Guess, Question, RoundSpec
from q20.shared.config import AppConfig, ConfigLoader
from q20.shared.exceptions import ConfigError, VersionMismatchError


def _write_configs(d, version="1.00"):
    (d / "setup.json").write_text(json.dumps({
        "version": version, "project": {"group": "t"},
        "game": {"questions": 2, "options": 2, "seed": 1,
                 "scoring": {"win": 3, "tie": 1, "loss": 1, "judge": 2},
                 "corpus": {"source": "bundled", "path": "data/corpus.sample.json"}},
    }), encoding="utf-8")
    (d / "models.json").write_text(json.dumps({
        "version": version, "provider": "ollama",
        "agents": {"default": {"model": "m", "temperature": 0.1}},
    }), encoding="utf-8")
    (d / "rate_limits.json").write_text(json.dumps({
        "version": version,
        "services": {"default": {"requests_per_minute": 1, "concurrent_max": 1,
                                 "retry_after_seconds": 1, "max_retries": 1}},
        "cost": {"max_cost_usd_per_run": 1.0},
    }), encoding="utf-8")


def test_load_minimal_config(tmp_path):
    _write_configs(tmp_path)
    cfg = ConfigLoader(tmp_path).load()
    assert isinstance(cfg, AppConfig)
    assert cfg.provider == "ollama"


def test_version_mismatch_fails_fast(tmp_path):
    _write_configs(tmp_path, version="9.99")
    with pytest.raises(VersionMismatchError):
        ConfigLoader(tmp_path).load()


def test_model_for_falls_back_to_default(tmp_path):
    _write_configs(tmp_path)
    cfg = ConfigLoader(tmp_path).load()
    assert cfg.model_for("anything").model == "m"


def test_model_for_raises_without_default():
    cfg = AppConfig(setup={}, models={}, provider="ollama",
                    ollama_base_url="x", limits={}, max_cost_usd=1.0)
    with pytest.raises(ConfigError):
        cfg.model_for("judge")


def test_invalid_json_config_raises(tmp_path):
    _write_configs(tmp_path)
    (tmp_path / "setup.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ConfigError):
        ConfigLoader(tmp_path).load()


def test_roundspec_public_view_and_from_paragraph():
    p = Paragraph("para", "open.", "word", "hint", ["a", "b"])
    spec = RoundSpec.from_paragraph(p)
    assert spec.public_view() == {"hint": "hint", "chain": ["a", "b"]}
    assert spec.opening_sentence == "open."


def test_round_carriers_are_plain_dataclasses():
    assert Question("t", ["a"]).options == ["a"]
    assert Guess("s", "w").associative_word == "w"


def test_role_other():
    from q20.constants import Role
    assert Role.JUDGE.other() is Role.PLAYER
    assert Role.PLAYER.other() is Role.JUDGE
