"""Unit tests for the MCP session objects — the leak-guard and payload adapters.

These exercise ``JudgeSession``/``PlayerSession`` directly (no FastMCP, no network:
``fastmcp`` is only imported inside ``build``/``main``, which we never call). The
critical invariant covered is the referee leak-guard: ``reveal`` is refused until a
guess is committed, so the judge can never leak the answer mid-round."""

import random

from q20.agents.factory import fake_agents
from q20.constants import Role
from q20.mcp.judge_server import JudgeSession
from q20.mcp.player_server import PlayerSession


def _judge_session(cfg, corpus):
    judge = fake_agents(cfg)[Role.JUDGE.value]
    return JudgeSession(judge, corpus, random.Random(cfg.setup["game"]["seed"]))


def test_publish_returns_only_public_view(cfg, corpus):
    view = _judge_session(cfg, corpus).public_view()
    assert set(view) == {"hint", "chain"}
    assert "opening_sentence" not in view and "associative_word" not in view


def test_reveal_is_refused_before_commit(cfg, corpus):
    out = _judge_session(cfg, corpus).reveal()
    assert out["revealed"] is False
    assert "opening_sentence" not in out


def test_reveal_succeeds_after_commit(cfg, corpus):
    s = _judge_session(cfg, corpus)
    s.commit_guess()
    out = s.reveal()
    assert out["revealed"] is True
    assert out["opening_sentence"] == s.spec.opening_sentence
    assert out["associative_word"] == s.spec.associative_word


def test_judge_session_answers_question_dicts(cfg, corpus):
    s = _judge_session(cfg, corpus)
    answers = s.answer([{"text": "q", "options": ["a", "b"]},
                        {"text": "q2", "options": ["c", "d"]}])
    assert answers == [0, 0]  # FakeJudge always picks index 0


def test_player_session_ask_returns_json_dicts(cfg):
    player = fake_agents(cfg)[Role.PLAYER.value]
    qs = PlayerSession(player).ask({"chain": ["a", "b"]})
    assert len(qs) == cfg.setup["game"]["questions"]
    assert all(set(q) == {"text", "options"} for q in qs)


def test_player_session_guess_returns_json_dict():
    class _P:
        def guess(self, view, qa):
            from q20.game.round import Guess
            return Guess("S", "W")
    out = PlayerSession(_P()).guess({}, [])
    assert out == {"opening_sentence": "S", "associative_word": "W"}
