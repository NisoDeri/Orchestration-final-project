"""Unit tests for the shared layer: cost, gatekeeper, version, config, protocol."""

import pytest

from q20.agents import protocol
from q20.shared.config import ConfigLoader
from q20.shared.cost import CostTracker, Usage
from q20.shared.exceptions import (
    ConfigError,
    CostCapExceededError,
    VersionMismatchError,
)
from q20.shared.gatekeeper import Gatekeeper, ServiceLimits
from q20.shared.version import CODE_VERSION, validate_config_version


def test_version_validation():
    validate_config_version(CODE_VERSION, "ok.json")
    with pytest.raises(VersionMismatchError):
        validate_config_version("0.99", "bad.json")


def test_cost_pricing_local_is_free():
    assert CostTracker.price(Usage(100, 100, "ollama")) == 0.0


def test_cost_pricing_cloud_and_cap():
    t = CostTracker(max_usd_per_run=0.0)
    with pytest.raises(CostCapExceededError):
        t.record("svc", Usage(1_000_000, 0, "claude-opus-4-8"), 1.0)


def test_cost_report_and_total():
    t = CostTracker(max_usd_per_run=10.0)
    t.record("ollama", Usage(5, 5, "ollama"), 0.1)
    assert t.report()["ollama"]["calls"] == 1
    assert t.total_usd() == 0.0


def test_gatekeeper_executes_and_retries():
    limits = {"default": ServiceLimits(120, 2, 0.0, 2)}
    g = Gatekeeper(limits, CostTracker(1.0))
    assert g.execute(lambda x: x + 1, 1) == 2
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    assert g.execute(flaky) == "ok"


def test_config_loads(cfg):
    assert cfg.setup["game"]["questions"] == 20
    assert cfg.model_for("judge").model
    assert cfg.model_for("unknown-role").model  # falls back to default


def test_config_missing_dir(tmp_path):
    with pytest.raises(ConfigError):
        ConfigLoader(tmp_path).load()


def test_build_gatekeeper(cfg):
    g = ConfigLoader.build_gatekeeper(cfg)
    assert g.execute(lambda: 42) == 42


def test_protocol_parsers_tolerant():
    assert protocol.parse_questions("garbage", 4) == []
    assert protocol.parse_answers("nope", 3) == [0, 0, 0]
    assert protocol.parse_guess("nope") == {"opening_sentence": "", "associative_word": ""}
    qs = protocol.parse_questions('[{"text":"t","options":["a","b"]}]', 4)
    assert qs[0]["options"] == ["a", "b"]
