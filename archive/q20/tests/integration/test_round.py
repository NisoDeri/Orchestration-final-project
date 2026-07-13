"""Integration: a full Judge-vs-Player round + the league skeleton, with fakes."""

from q20.agents.factory import fake_agents
from q20.constants import Outcome, Role
from q20.sdk.sdk import get_report, run_league, run_round


def test_full_fake_round_is_a_scored_win(cfg, corpus):
    agents = fake_agents(cfg)
    log = run_round(agents[Role.JUDGE.value], agents[Role.PLAYER.value], corpus, cfg)
    assert log["outcome"] == Outcome.WIN  # perfect fake player reconstructs the answer
    assert len(log["questions"]) == cfg.setup["game"]["questions"]
    grid = cfg.setup["game"]["scoring"]
    assert log["scores"][Role.PLAYER.value] == grid["win"]
    assert log["scores"][Role.JUDGE.value] == grid["judge"]
    assert log["guess"] == log["truth"]


def test_report_summary(cfg, corpus):
    agents = fake_agents(cfg)
    log = run_round(agents[Role.JUDGE.value], agents[Role.PLAYER.value], corpus, cfg)
    rep = get_report(log)
    assert rep["correct"] is True
    assert rep["questions_asked"] == cfg.setup["game"]["questions"]


def test_league_skeleton_round_robin(cfg, corpus):
    groups = ["g1", "g2", "g3"]

    def make(gid, role):
        return corpus if gid == "corpus" else fake_agents(cfg)[role.value]

    result = run_league(cfg, groups, make)
    assert set(result["standings"]) == set(groups)
    # 3 groups -> 6 ordered pairs -> 6 rounds played
    assert len(result["rounds"]) == 6
    assert result["ranking"][0] in groups
    assert all(v > 0 for v in result["standings"].values())
