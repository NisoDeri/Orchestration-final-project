"""Unit tests for the SDK orchestrator: run_round determinism, log schema,
the reveal seam, get_report, and league standings/ranking math."""

import random

from q20.agents.factory import fake_agents
from q20.constants import Outcome, Role
from q20.game.round import Guess, RoundSpec
from q20.sdk.sdk import assemble_log, get_report, run_league, run_round


def _make(cfg, corpus):
    def make(gid, role):
        return corpus if gid == "corpus" else fake_agents(cfg)[role.value]
    return make


def test_run_round_is_deterministic_with_explicit_rng(cfg, corpus):
    agents = fake_agents(cfg)
    a = run_round(agents["judge"], agents["player"], corpus, cfg, random.Random(42))
    b = run_round(agents["judge"], agents["player"], corpus, cfg, random.Random(42))
    assert a["truth"] == b["truth"]
    assert a["guess"] == b["guess"]
    assert a["outcome"] == b["outcome"]


def test_run_round_uses_config_seed_when_rng_omitted(cfg, corpus):
    agents = fake_agents(cfg)
    a = run_round(agents["judge"], agents["player"], corpus, cfg)
    b = run_round(agents["judge"], agents["player"], corpus, cfg)
    assert a["truth"] == b["truth"]  # both fall back to the same config seed


def test_round_log_has_canonical_schema(cfg, corpus):
    agents = fake_agents(cfg)
    log = run_round(agents["judge"], agents["player"], corpus, cfg)
    for key in ("group_name", "students", "github_repo", "public_view",
                "questions", "guess", "truth", "outcome", "scores", "models"):
        assert key in log
    assert log["group_name"] == cfg.setup["project"]["group"]
    assert log["models"][Role.JUDGE.value] == cfg.model_for("judge").model
    assert log["models"][Role.PLAYER.value] == cfg.model_for("player").model


def test_public_view_never_leaks_the_answer(cfg, corpus):
    agents = fake_agents(cfg)
    log = run_round(agents["judge"], agents["player"], corpus, cfg)
    assert set(log["public_view"]) == {"hint", "chain"}
    assert "opening_sentence" not in log["public_view"]
    assert "associative_word" not in log["public_view"]


def test_assemble_log_marks_loss_and_mismatch(cfg):
    spec = RoundSpec("p", "the truth.", "word", "h", ["a"])
    guess = Guess("wrong", "wrong")
    log = assemble_log(cfg, spec, [], guess, Outcome.LOSS, {"player": 1, "judge": 2})
    assert log["outcome"] == Outcome.LOSS
    assert get_report(log)["correct"] is False


def test_get_report_counts_questions(cfg, corpus):
    agents = fake_agents(cfg)
    log = run_round(agents["judge"], agents["player"], corpus, cfg)
    rep = get_report(log)
    assert rep["questions_asked"] == cfg.setup["game"]["questions"]
    assert rep["correct"] is True
    assert rep["outcome"] == Outcome.WIN


def test_league_standings_sum_per_round(cfg, corpus):
    groups = ["g1", "g2"]
    result = run_league(cfg, groups, _make(cfg, corpus))
    grid = cfg.setup["game"]["scoring"]
    # 2 groups -> 2 ordered pairs; each group judges once (+judge) and plays once (+win).
    expected = grid["judge"] + grid["win"]
    assert all(v == expected for v in result["standings"].values())


def test_league_ranking_is_sorted_desc(cfg, corpus):
    groups = ["a", "b", "c"]
    result = run_league(cfg, groups, _make(cfg, corpus))
    points = [result["standings"][g] for g in result["ranking"]]
    assert points == sorted(points, reverse=True)


def test_league_skips_self_pairing(cfg, corpus):
    groups = ["x", "y", "z"]
    result = run_league(cfg, groups, _make(cfg, corpus))
    assert all(r["judge"] != r["player"] for r in result["rounds"])
    assert len(result["rounds"]) == len(groups) * (len(groups) - 1)


def test_league_single_group_plays_nothing(cfg, corpus):
    result = run_league(cfg, ["solo"], _make(cfg, corpus))
    assert result["rounds"] == []
    assert result["standings"] == {"solo": 0}
