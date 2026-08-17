"""SDK orchestration tests — full fake-opponent series, alternation, timeout, lab gate.

Everything is in-process: FakeTransport pairs, injected keypairs/sysinfo/commit, tmp
config dirs. No sockets, no subprocesses, no LLMs (the CI gate).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from pursuit.domain.crypto import generate_keypair
from pursuit.infra.transport import FakeTransport
from pursuit.peer.agreement import build_agreement_message
from pursuit.peer.inboxes import PeerInboxes
from pursuit.sdk import run_lab, run_peer
from pursuit.sdk.series import ScentBelief, logical_subgame_numbers
from pursuit.sdk.series_log import emit_artifacts, log_document, write_json
from pursuit.shared.config import ConfigManager
from pursuit.constants import Role

GID = "nis-yar1"
OUR_FULL_SHA = "a" * 40
THEIR_FULL_SHA = "b" * 40
SPEC = {"os": "TestOS", "cpu_type": "TestCPU", "cpu_freq_mhz": 1, "cpu_cores": 1,
        "ram_gb": 1.0, "gpu_model": "none", "vram_gb": 0.0}

GAME_TOML = """
version = "0.1.0"

[game]
group_id = "{gid}"
group_name = "Test Group"
members = ["A", "B"]
sub_game_number = 1
repos = {{ cop = "https://x/c", thief = "https://x/t" }}
mcp_servers = {{ cop = "http://c/mcp", thief = "http://t/mcp" }}

[network]
my_port = 8802
opponent_url = "http://127.0.0.1:8801/mcp"
turn_timeout_seconds = {turn}
brain_deadline_seconds = 0.0
poll_interval_seconds = 0.01
connect_timeout_seconds = 5.0
retry_interval_seconds = 0.01
audit_send_timeout_seconds = {audit}

[fsm]
max_illegal_events = 3

[trash_talk]
model = "stub"

[play]
seed = 11

[paths]
logs_dir = "logs"
"""


def make_game(num_games=1, survival=6, max_moves=6) -> dict:
    return {
        "agreed_between": ["anrbj666", "nis-yar1"],
        "board_and_agents": {"grid_size": 7, "thief_start": [3, 3], "cop_start": [0, 0],
                             "axis_origin_corner": "top-left", "axis_start_index": 0},
        "world": {"map_area": "New York", "hint_max_words": 15},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                                  "max_barriers": 3, "max_moves": max_moves,
                                  "survival_threshold": survival},
        "scoring": {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                    "survival_thief": 10, "tie_score": 2, "technical_loss": 0},
        "pheromones": {"dialect": "book", "pheromone_center_intensity": 0.9,
                       "pheromone_decay": 0.1, "pheromone_grid_size": 5,
                       "pheromone_min_center_intensity": 0.5},
        "crypto": {"dialect": "book"},
        "network_and_league": {"num_games": num_games, "watchdog_timeout_sec": 60},
    }


def write_config(base: Path, *, num_games=1, turn=10.0, audit=5.0) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    (base / "game.json").write_text(json.dumps(make_game(num_games)), encoding="utf-8")
    (base / "game.toml").write_text(GAME_TOML.format(gid=GID, turn=turn, audit=audit),
                                    encoding="utf-8")
    (base / "rate_limits.json").write_text("{}", encoding="utf-8")
    return base


def run_fake(config_dir: Path, tmp_path: Path, role="police", num_games=1):
    return run_peer(config_dir, role, num_games=num_games, fake_opponent=True,
                    logs_dir=tmp_path / "logs", sysinfo=SPEC, github_commit="abc1234",
                    keypair=generate_keypair(), rng=random.Random(3))


class TestFakeOpponentSeries:
    def test_full_subgame_reaches_a_real_outcome_with_audit(self, tmp_path):
        summary = run_fake(write_config(tmp_path / "cfg"), tmp_path)
        assert summary["num_sub_games"] == 1
        sub = summary["sub_games"][0]
        assert sub["result"] in ("capture", "survival")  # a REAL outcome, never timeout
        assert sub["winner_role"] in ("police", "thief")
        assert sub["audit"]["passed"] is True
        assert sub["audit"]["failed_steps"] == []
        assert summary["game_id"] == f"{GID}-vs-{GID}-fake"  # sorted gids (INTEROP §3.2)

    def test_series_totals_follow_the_signed_scoring_table(self, tmp_path):
        summary = run_fake(write_config(tmp_path / "cfg"), tmp_path)
        sub = summary["sub_games"][0]
        assert summary["totals"][GID] == sub["score"][GID]
        assert summary["totals"][f"{GID}-fake"] == sub["score"][f"{GID}-fake"]
        winners = {True: GID, False: f"{GID}-fake"}
        if not summary["tie"]:
            top = max(summary["totals"], key=summary["totals"].get)
            assert summary["winner"] == top
            assert summary["winner"] in winners.values()

    def test_log_files_written_per_subgame_and_series(self, tmp_path):
        summary = run_fake(write_config(tmp_path / "cfg"), tmp_path)
        log_dir = tmp_path / "logs" / GID
        log_file = log_dir / f"log_{summary['game_id']}_g01.json"
        series_file = log_dir / f"series_{summary['game_id']}.json"
        assert log_file.exists() and series_file.exists()
        document = json.loads(log_file.read_text(encoding="utf-8"))
        assert document["summary"]["role"] == "police"
        assert document["records"][0]["payload"]["type"] == "system_spec"
        assert document["records"][0]["payload"]["github_commit"] == "abc1234"
        assert all({"payload", "nonce", "commit"} <= set(r) for r in document["records"])
        assert json.loads(series_file.read_text(encoding="utf-8"))["group_id"] == GID

    def test_role_alternation_across_two_subgames(self, tmp_path):
        summary = run_fake(write_config(tmp_path / "cfg", num_games=2), tmp_path,
                           num_games=2)
        roles = [sub["roles"][GID] for sub in summary["sub_games"]]
        assert roles == ["police", "thief"]  # odd = my config role (reference alternation)
        assert [sub["sub_game_number"] for sub in summary["sub_games"]] == [1, 2]
        assert all(sub["audit"]["passed"] for sub in summary["sub_games"])

    def test_num_games_defaults_to_the_signed_config(self, tmp_path):
        summary = run_fake(write_config(tmp_path / "cfg", num_games=1), tmp_path,
                           num_games=None)
        assert summary["num_sub_games"] == 1  # network_and_league.num_games, not a literal

    def test_fixed_role_uses_pairing_window_numbers(self, tmp_path):
        cfg = ConfigManager.load(write_config(tmp_path / "cfg", num_games=6))
        assert logical_subgame_numbers(cfg, Role.THIEF, 3, alternate=False) == [1, 3, 5]
        assert logical_subgame_numbers(cfg, Role.POLICE, 3, alternate=False) == [2, 4, 6]

    def test_fixed_role_explicit_odd_role_overrides_pair_sort(self, tmp_path):
        cfg = ConfigManager.load(write_config(tmp_path / "cfg", num_games=6))
        cfg.set_private("game.fixed_role_odd", "police")
        assert logical_subgame_numbers(cfg, Role.POLICE, 3, alternate=False) == [1, 3, 5]
        assert logical_subgame_numbers(cfg, Role.THIEF, 3, alternate=False) == [2, 4, 6]

    def test_fixed_role_artifact_emit_merges_sibling_endpoint_logs(self, tmp_path):
        cfg = ConfigManager.load(write_config(tmp_path / "cfg", num_games=6))
        out_dir = tmp_path / "logs" / GID
        keypair = generate_keypair()

        class Outcome:
            result = type("R", (), {"value": "capture"})()
            winner = Role.POLICE
            scores = {Role.POLICE: 20, Role.THIEF: 5}
            audit = {"passed": True, "forgery": False, "opponent_received": True,
                     "failed_steps": [],
                     "their_records": [
                         {"payload": {"step": 0, "github_commit": THEIR_FULL_SHA},
                          "nonce": "n2", "commit": "c2"},
                         {"payload": {"step": 1, "tokens_total": 34},
                          "nonce": "n4", "commit": "c4"},
                     ]}
            records = [{"payload": {"step": 0, "sub_game_number": 1,
                                    "github_commit": OUR_FULL_SHA},
                        "nonce": "n", "commit": "c"},
                       {"payload": {"step": 1, "tokens_total": 12},
                        "nonce": "n3", "commit": "c3"}]
            steps = 8
            end_state_digest = "digest"
            game_id = "anrbj666-vs-nis-yar1"
            game_uid = "uid"
            opponent_group = "anrbj666"
            opponent_identity = {
                "group_id": "anrbj666",
                "members": ["Alon", "Renat"],
                "repos": {"cop": "https://gh/anrbj666/cop"},
                "mcp_servers": {"cop": "https://cop-mcp.alon.website/mcp"},
                "llm_model": "qwen3:14b",
            }

        first = log_document(1, Role.THIEF, GID, Outcome())
        write_json(out_dir / "log_anrbj666-vs-nis-yar1_g01.json", first)
        second = log_document(3, Role.THIEF, GID, Outcome())
        summary = {"game_id": "anrbj666-vs-nis-yar1", "group_id": GID,
                   "num_sub_games": 1, "config_sha256": "abc123",
                   "sub_games": [], "totals": {GID: 0, "anrbj666": 0},
                   "tie": True, "winner": None}

        emit_artifacts(cfg, summary, [second], SPEC, OUR_FULL_SHA, keypair, out_dir)

        result = json.loads((out_dir / "result_anrbj666-vs-nis-yar1.json")
                            .read_text(encoding="utf-8"))
        assert [row["sub_game_number"] for row in result["sub_games"]] == [1, 3]
        assert result["num_sub_games"] == 2
        assert result["links"]["github"]["nis-yar1"] == {
            "cop": "https://x/c", "thief": "https://x/t"}
        assert result["links"]["github"]["anrbj666"] == {"cop": "https://gh/anrbj666/cop"}
        assert result["sub_games"][0]["github_commit"] == {
            "nis-yar1": OUR_FULL_SHA, "anrbj666": THEIR_FULL_SHA}
        assert result["sub_games"][0]["tokens"] == {
            "nis-yar1": 12, "anrbj666": 34}
        # the merge pulled the sibling endpoint's row (result rows are template-trimmed now)
        assert "end_state_digest" not in result["sub_games"][0]
        assert result["sub_games"][0]["audit"]["log_verified"] is True
        assert (out_dir / "config_anrbj666-vs-nis-yar1_g01.json").exists()
        assert (out_dir / "config_anrbj666-vs-nis-yar1_g03.json").exists()
        declaration = json.loads((out_dir / "declaration_anrbj666-vs-nis-yar1.json")
                                 .read_text(encoding="utf-8"))
        assert declaration["llm_model"] == "stub"
        assert declaration["groups"]["group_2"]["members"] == ["Alon", "Renat"]


class TestTimeoutPath:
    def test_opponent_silence_scores_technical_loss_and_still_audits(self, tmp_path):
        config_dir = write_config(tmp_path / "cfg", turn=0.3, audit=0.3)
        inboxes = PeerInboxes()
        transport = FakeTransport(PeerInboxes())  # a sink nobody ever answers from
        opponent = ConfigManager(
            game_terms=make_game(), rate_limits={},
            private_terms={"game": {"group_id": "zz-team", "group_name": "ZZ",
                                    "members": ["Z"], "repos": {}, "mcp_servers": {}},
                           "trash_talk": {"model": "stub"},
                           "network": {"connect_timeout_seconds": 5,
                                       "retry_interval_seconds": 0.01,
                                       "poll_interval_seconds": 0.01}})
        inboxes.negotiation.put(build_agreement_message(opponent, generate_keypair()[1]))
        summary = run_peer(config_dir, "police", num_games=1, transport=transport,
                           inboxes=inboxes, logs_dir=tmp_path / "logs", sysinfo=SPEC,
                           github_commit="abc1234", keypair=generate_keypair())
        sub = summary["sub_games"][0]
        assert sub["result"] == "technical_loss"  # ruling A6 — 0/0, never waiting-peer-wins
        assert sub["score"] == {GID: 0, "zz-team": 0}
        assert sub["winner_role"] is None
        assert "submit_audit" in [tool for tool, _ in transport.sent]  # audit STILL ran
        assert (tmp_path / "logs" / GID / f"log_{summary['game_id']}_g01.json").exists()


class TestScentBelief:
    def test_starts_at_the_opponent_signed_start_cell(self):
        belief = ScentBelief((3, 3))
        assert belief.most_likely() == (3, 3)
        assert belief.most_likely_p() == 1.0

    def test_observe_smell_tracks_strongest_cell_row_major_ties(self):
        belief = ScentBelief((0, 0))
        belief.observe_smell({"1,1": 0.5, "0,2": 0.5, "4,4": 0.3})
        assert belief.most_likely() == (0, 2)  # tie broken row-major
        belief.observe_smell({})  # empty snapshot: keep the last mode
        assert belief.most_likely() == (0, 2)
        belief.diffuse("police", (0, 0))  # PREDICT no-op never crashes the handler seam


class TestLabGate:
    def test_run_lab_paired_seeds_through_the_sdk_only(self, tmp_path):
        config_dir = write_config(tmp_path / "cfg")
        report = run_lab(2, 5, "pursuit.strategy.greedy:GreedyPoliceBrain",
                         "pursuit.strategy.greedy:GreedyThiefBrain", config_dir)
        assert report["games"] == 4  # 2 seeds x both role assignments (§6.3 pairing)
        assert 0.0 <= report["win_rate_A"] <= 1.0
        assert 0.0 <= report["p_value_A"] <= 1.0
        assert set(report["points"]) == {"A", "B"}

    def test_run_lab_rejects_a_non_brain_selector(self, tmp_path):
        from pursuit.exceptions import ConfigError

        config_dir = write_config(tmp_path / "cfg")
        with pytest.raises(ConfigError, match="BrainBase"):
            run_lab(1, 1, "pursuit.shared.config:ConfigManager",
                    "pursuit.strategy.greedy:GreedyThiefBrain", config_dir)
