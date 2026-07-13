"""The LLM brains must never let a flaky/raising model crash a round.

When the injected client raises, the Judge falls back to all-zero answers and the
Player falls back to padded filler questions / an empty guess — so the engine still
produces a scored round. These cover the defensive ``except`` branches."""

from q20.agents.judge import JudgeAgent
from q20.agents.player import PlayerAgent
from q20.game.round import Question
from q20.shared.config import AgentModel


class _RaisingClient:
    def chat(self, *a, **k):
        raise RuntimeError("model exploded")


class _Gate:
    def execute(self, fn, *args, service="default", usage_of=None, **kwargs):
        return fn(*args, **kwargs)


def test_judge_answers_zero_when_model_raises():
    j = JudgeAgent(_RaisingClient(), _Gate(), AgentModel("m", 0.0))
    qs = [Question("q", ["a", "b"]) for _ in range(3)]
    # spec is unused on the failure path; None proves we never touch it after the raise.
    assert j.answer(_DummySpec(), qs) == [0, 0, 0]


class _DummySpec:
    paragraph = "secret"


def test_player_pads_fillers_when_ask_raises():
    p = PlayerAgent(_RaisingClient(), _Gate(), AgentModel("m", 0.0), 4, 3)
    qs = p.ask({"chain": ["a", "b"]})
    assert len(qs) == 4
    assert all(len(q.options) == 3 for q in qs)


def test_player_empty_guess_when_guess_raises():
    p = PlayerAgent(_RaisingClient(), _Gate(), AgentModel("m", 0.0), 4, 3)
    g = p.guess({"chain": ["a"]}, [])
    assert g.opening_sentence == "" and g.associative_word == ""


def test_player_filler_handles_missing_chain():
    p = PlayerAgent(_RaisingClient(), _Gate(), AgentModel("m", 0.0), 2, 4)
    qs = p.ask({})  # no chain key -> filler uses its default topic
    assert len(qs) == 2 and all(q.options for q in qs)
