"""Integration tests for the thin CLI: play-round (fake), run-league, report.

These drive the real argument parser + SDK end-to-end with the deterministic fake
agents (no model, no network) and assert the on-disk artifacts the league consumes.
"""

import json

from q20.cli.main import build_parser, main


def test_parser_requires_a_subcommand():
    import pytest
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_play_round_fake_writes_scored_log(tmp_path, capsys):
    out = tmp_path / "art"
    main(["play-round", "--fake", "--out", str(out)])
    log = json.loads((out / "round_log.json").read_text(encoding="utf-8"))
    assert log["outcome"] == "win"
    assert log["guess"] == log["truth"]
    assert "round complete" in capsys.readouterr().out


def test_run_league_writes_standings(tmp_path, capsys):
    out = tmp_path / "league"
    main(["run-league", "--groups", "g1", "g2", "g3", "--out", str(out)])
    result = json.loads((out / "league.json").read_text(encoding="utf-8"))
    assert set(result["standings"]) == {"g1", "g2", "g3"}
    assert len(result["rounds"]) == 6
    assert "ranking" in capsys.readouterr().out


def test_run_league_default_groups(tmp_path):
    out = tmp_path / "lg"
    main(["run-league", "--out", str(out)])
    result = json.loads((out / "league.json").read_text(encoding="utf-8"))
    assert len(result["standings"]) == 3  # us + two rivals


def test_report_reads_existing_log(tmp_path, capsys):
    out = tmp_path / "art"
    main(["play-round", "--fake", "--out", str(out)])
    capsys.readouterr()
    main(["report", str(out / "round_log.json")])
    rep = json.loads(capsys.readouterr().out)
    assert rep["correct"] is True
    assert rep["outcome"] == "win"
