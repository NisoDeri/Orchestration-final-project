"""Unit tests for the deterministic fakes and the LLM brains (fake client)."""

import random

from q20.agents.factory import fake_agents
from q20.agents.fake import FakeJudge, FakePlayer
from q20.agents.judge import JudgeAgent
from q20.agents.player import PlayerAgent
from q20.game.round import Question
from q20.shared.config import AgentModel
from q20.shared.cost import Usage


def test_fake_judge_selects_and_answers(corpus):
    j = FakeJudge()
    spec = j.select(corpus, random.Random(3))
    qs = [Question("q", ["a", "b"]) for _ in range(5)]
    answers = j.answer(spec, qs)
    assert answers == [0, 0, 0, 0, 0]


def test_fake_player_asks_n_questions(cfg):
    p = FakePlayer(cfg.setup["game"]["questions"], cfg.setup["game"]["options"])
    qs = p.ask({"chain": ["x", "y"]})
    assert len(qs) == cfg.setup["game"]["questions"]
    assert all(len(q.options) == cfg.setup["game"]["options"] for q in qs)


def test_fake_player_guesses_from_revealed_answer():
    p = FakePlayer(2, 4)
    g = p.guess({"_answer_sentence": "S", "_answer_word": "W"}, [])
    assert g.opening_sentence == "S" and g.associative_word == "W"


def test_factory_builds_fakes(cfg):
    agents = fake_agents(cfg)
    assert agents["judge"].role == "judge"
    assert agents["player"].role == "player"


class _FakeClient:
    """Returns canned replies in order, with token usage, like OllamaClient.chat."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0

    def chat(self, model, messages, temperature=0.0, num_ctx=None):
        from q20.shared.ollama_client import ChatResult
        text = self._replies[self.calls] if self.calls < len(self._replies) else "{}"
        self.calls += 1
        return ChatResult(text=text, usage=Usage(1, 1, model))


class _DirectGate:
    """Minimal gatekeeper double: call straight through (no limits in tests)."""

    def execute(self, fn, *args, service="default", usage_of=None, **kwargs):
        return fn(*args, **kwargs)


def test_llm_judge_answers_parsed(corpus):
    client = _FakeClient(["[1, 2, 0]"])
    j = JudgeAgent(client, _DirectGate(), AgentModel("m", 0.0))
    spec = j.select(corpus, random.Random(1))
    qs = [Question("q", ["a", "b", "c"]) for _ in range(3)]
    answers = j.answer(spec, qs)
    assert answers == [1, 2, 0]


def test_llm_judge_clamps_out_of_range(corpus):
    client = _FakeClient(["[9]"])
    j = JudgeAgent(client, _DirectGate(), AgentModel("m", 0.0))
    spec = j.select(corpus, random.Random(1))
    answers = j.answer(spec, [Question("q", ["a", "b"])])
    assert answers == [1]  # clamped to last valid index


def test_llm_judge_empty_questions():
    j = JudgeAgent(_FakeClient([]), _DirectGate(), AgentModel("m", 0.0))
    assert j.answer(None, []) == []


def test_llm_player_pads_short_batch():
    reply = '[{"text": "q1", "options": ["a", "b", "c", "d"]}]'
    guess = '{"opening_sentence": "S", "associative_word": "W"}'
    p = PlayerAgent(_FakeClient([reply, guess]), _DirectGate(), AgentModel("m", 0.0), 4, 4)
    view = {"hint": "h", "chain": ["c"]}
    qs = p.ask(view)
    assert len(qs) == 4  # 1 parsed + 3 padded
    g = p.guess(view, [])
    assert g.opening_sentence == "S" and g.associative_word == "W"


def test_llm_player_handles_garbage():
    p = PlayerAgent(_FakeClient(["not json", "also not json"]), _DirectGate(),
                    AgentModel("m", 0.0), 2, 3)
    qs = p.ask({"chain": ["z"]})
    assert len(qs) == 2
    g = p.guess({}, [])
    assert g.opening_sentence == ""
