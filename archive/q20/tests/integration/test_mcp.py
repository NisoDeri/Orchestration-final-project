"""MCP layer tests — sessions + the over-the-wire orchestrator, NO fastmcp/network.

We exercise ``JudgeSession``/``PlayerSession`` (the logic the ``@mcp.tool`` wrappers
delegate to) directly with the deterministic fake agents, and drive
``run_round_over_mcp`` against in-memory fake clients that mimic the wire. ``build()``
(the only fastmcp consumer) stays untouched so these run with fastmcp uninstalled.
"""

import asyncio
import random

from q20.agents.fake import FakeJudge, FakePlayer
from q20.constants import Outcome
from q20.mcp import client as mcp_client
from q20.mcp.judge_server import JudgeSession
from q20.mcp.player_server import PlayerSession


def test_judge_session_publishes_view_without_leaking(corpus):
    session = JudgeSession(FakeJudge(), corpus, random.Random(7))
    view = session.public_view()
    assert set(view) == {"hint", "chain"}
    assert "opening_sentence" not in view and "paragraph" not in view


def test_judge_session_reveal_is_leak_guarded(corpus):
    session = JudgeSession(FakeJudge(), corpus, random.Random(7))
    assert session.reveal() == {"revealed": False, "reason": "guess not yet committed"}
    session.commit_guess()
    revealed = session.reveal()
    assert revealed["revealed"] is True
    assert revealed["opening_sentence"] == session.spec.opening_sentence


def test_judge_session_answers_match_question_count(corpus):
    session = JudgeSession(FakeJudge(), corpus, random.Random(7))
    answers = session.answer([{"text": "q1", "options": ["a", "b"]},
                              {"text": "q2", "options": ["c", "d"]}])
    assert answers == [0, 0]


def test_player_session_ask_and_guess_roundtrip(corpus):
    spec = JudgeSession(FakeJudge(), corpus, random.Random(7)).spec
    session = PlayerSession(FakePlayer(20, 4))
    view = {"hint": spec.hint, "chain": list(spec.chain),
            "_answer_sentence": spec.opening_sentence, "_answer_word": spec.associative_word}
    questions = session.ask(view)
    assert len(questions) == 20
    assert all(len(q["options"]) == 4 for q in questions)
    guess = session.guess(view, [])
    assert guess["opening_sentence"] == spec.opening_sentence


class _FakeJudgeClient:
    """In-memory stand-in for ``JudgeClient`` (no network)."""

    def __init__(self, session: JudgeSession):
        self._s = session

    async def publish(self):
        return self._s.public_view()

    async def answer(self, questions):
        return self._s.answer(questions)

    async def commit_guess(self):
        self._s.commit_guess()
        return {"ok": True}

    async def reveal(self):
        return self._s.reveal()


class _FakePlayerClient:
    """In-memory stand-in for ``PlayerClient`` that also leaks the answer onto the view."""

    def __init__(self, session: PlayerSession, spec):
        self._s = session
        self._spec = spec

    async def ask(self, view):
        view["_answer_sentence"] = self._spec.opening_sentence
        view["_answer_word"] = self._spec.associative_word
        return self._s.ask(view)

    async def guess(self, view, qa):
        view["_answer_sentence"] = self._spec.opening_sentence
        view["_answer_word"] = self._spec.associative_word
        return self._s.guess(view, qa)


def test_run_round_over_mcp_assembles_scored_log(cfg, corpus, monkeypatch):
    judge_session = JudgeSession(FakeJudge(), corpus, random.Random(7))
    player_session = PlayerSession(FakePlayer(20, 4))
    monkeypatch.setattr(mcp_client, "JudgeClient",
                        lambda url: _FakeJudgeClient(judge_session))
    monkeypatch.setattr(mcp_client, "PlayerClient",
                        lambda url: _FakePlayerClient(player_session, judge_session.spec))

    log = mcp_client.play_over_mcp(cfg, "http://j/mcp", "http://p/mcp")
    assert log["outcome"] == Outcome.WIN.value
    assert len(log["questions"]) == 20
    assert log["scores"]["player"] == cfg.setup["game"]["scoring"]["win"]
    assert log["guess"] == log["truth"]


def test_run_round_over_mcp_is_a_coroutine(cfg, corpus, monkeypatch):
    judge_session = JudgeSession(FakeJudge(), corpus, random.Random(7))
    player_session = PlayerSession(FakePlayer(20, 4))
    monkeypatch.setattr(mcp_client, "JudgeClient", lambda url: _FakeJudgeClient(judge_session))
    monkeypatch.setattr(mcp_client, "PlayerClient",
                        lambda url: _FakePlayerClient(player_session, judge_session.spec))
    log = asyncio.run(mcp_client.run_round_over_mcp(cfg, "http://j/mcp", "http://p/mcp"))
    assert log["outcome"] in {o.value for o in Outcome}
