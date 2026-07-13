"""Edge cases for the gatekeeper + cost tracker that the happy-path tests miss:
unknown-service fallback, rate-limit waiting, retry-budget exhaustion, and the
cost report/cap surfaces."""

import pytest

from q20.shared.cost import CostTracker, Usage
from q20.shared.exceptions import CostCapExceededError
from q20.shared.gatekeeper import Gatekeeper, ServiceLimits


def _gate(rpm=120, conc=2, retry_after=0.0, retries=1, cap=1.0):
    return Gatekeeper({"default": ServiceLimits(rpm, conc, retry_after, retries)},
                      CostTracker(cap))


def test_unknown_service_falls_back_to_default():
    g = _gate()
    assert g.execute(lambda: "ok", service="does-not-exist") == "ok"


def test_retry_budget_exhausted_reraises():
    g = _gate(retries=1)

    def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        g.execute(always_fail)


def test_rate_limit_wait_branch(monkeypatch):
    # Force the limiter to report "full once, then free" and capture the wait sleep,
    # so the wait-and-retry branch runs without actually blocking for a minute.
    g = _gate(rpm=1, retry_after=5.0)
    _service, _lim, window, _sem = g._resources("default")
    seq = iter([3.0, 0.0])  # first: wait 3s, second: slot free
    monkeypatch.setattr(window, "time_until_slot", lambda: next(seq))
    slept = []
    monkeypatch.setattr("time.sleep", slept.append)
    assert g.execute(lambda: 7) == 7
    assert slept == [3.0]  # waited min(3, retry_after=5) once, then proceeded


def test_cost_report_accumulates_calls_and_seconds():
    t = CostTracker(10.0)
    t.record("ollama", Usage(3, 4, "ollama"), 0.5)
    t.record("ollama", Usage(1, 1, "ollama"), 0.25)
    rep = t.report()["ollama"]
    assert rep["calls"] == 2
    assert rep["seconds"] == 0.75
    assert rep["usd"] == 0.0


def test_cost_cap_trips_on_cloud_model():
    t = CostTracker(0.001)
    with pytest.raises(CostCapExceededError):
        t.record("svc", Usage(1_000_000, 1_000_000, "claude-sonnet-4-6"), 1.0)


def test_price_unknown_model_is_free():
    assert CostTracker.price(Usage(10, 10, "some-unknown-model")) == 0.0


def test_cost_report_property_on_gatekeeper():
    g = _gate(cap=10.0)
    g.execute(lambda: 1, usage_of=lambda r: Usage(0, 0, "ollama"))
    assert "default" in g.cost_report
