"""Unit tests for pursuit.shared.config — ConfigManager over the real police tree."""

import json
import shutil
from pathlib import Path

import pytest

from pursuit.exceptions import ConfigError
from pursuit.shared.config import REQUIRED_AGREED_TERMS, ConfigManager

ROOT = Path(__file__).resolve().parents[2]
POLICE_DIR = ROOT / "config" / "police"


@pytest.fixture(scope="module")
def cfg() -> ConfigManager:
    return ConfigManager.load(POLICE_DIR)


def _clone_config(tmp_path: Path, mutate=None) -> Path:
    """Copy the police tree into tmp_path, optionally mutating game.json."""
    for name in ("game.toml", "rate_limits.json"):
        shutil.copy(POLICE_DIR / name, tmp_path / name)
    data = json.loads((POLICE_DIR / "game.json").read_text(encoding="utf-8"))
    if mutate is not None:
        mutate(data)
    (tmp_path / "game.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def _delete(data: dict, dotted: str) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]


class TestLoad:
    def test_loads_real_police_tree(self, cfg):
        assert cfg.game("board_and_agents.grid_size") == 7
        assert cfg.private("network.my_port") == 8802

    def test_missing_game_json(self, tmp_path):
        with pytest.raises(ConfigError, match="game.json"):
            ConfigManager.load(tmp_path)

    def test_missing_game_toml(self, tmp_path):
        shutil.copy(POLICE_DIR / "game.json", tmp_path / "game.json")
        with pytest.raises(ConfigError, match="game.toml"):
            ConfigManager.load(tmp_path)

    def test_invalid_json_rejected(self, tmp_path):
        _clone_config(tmp_path)
        (tmp_path / "game.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ConfigError, match="invalid JSON in game.json"):
            ConfigManager.load(tmp_path)

    def test_invalid_toml_rejected(self, tmp_path):
        _clone_config(tmp_path)
        (tmp_path / "game.toml").write_text("=broken=", encoding="utf-8")
        with pytest.raises(ConfigError, match="invalid TOML in game.toml"):
            ConfigManager.load(tmp_path)


class TestDottedAccess:
    def test_game_nested_paths(self, cfg):
        assert cfg.game("movement_and_barriers.move_set") == ["N", "S", "E", "W", "STAY"]
        assert cfg.game("pheromones.dialect") == "reference"
        assert cfg.game("crypto.dialect") == "reference"
        assert cfg.game("board_and_agents.thief_start") == [3, 3]

    def test_private_nested_paths(self, cfg):
        assert cfg.private("game.group_id") == "nis-yar1"
        assert cfg.private("belief.smell_trust_weight") == 4.0

    @pytest.mark.parametrize("path", ["nope", "scoring.nope", "scoring.tie_score.deeper"])
    def test_game_missing_path_names_term_and_file(self, cfg, path):
        with pytest.raises(ConfigError, match=f"'{path}' in game.json"):
            cfg.game(path)

    def test_private_missing_path_names_file(self, cfg):
        with pytest.raises(ConfigError, match="'network.nope' in game.toml"):
            cfg.private("network.nope")

    def test_service_limits(self, cfg):
        assert cfg.service_limits("gmail")["daily_quota"] == 50
        with pytest.raises(ConfigError, match="service 'slack' in rate_limits.json"):
            cfg.service_limits("slack")


class TestValidateAgreement:
    def test_passes_on_real_tree(self, cfg):
        cfg.validate_agreement()  # must not raise

    @pytest.mark.parametrize(
        "term",
        [
            "board_and_agents.grid_size",
            "board_and_agents.thief_start",
            "movement_and_barriers.move_set",
            "movement_and_barriers.max_barriers",
            "movement_and_barriers.survival_threshold",
            "scoring.tie_score",
        ],
    )
    def test_deleted_term_fails_naming_term_and_file(self, tmp_path, term):
        _clone_config(tmp_path, mutate=lambda d: _delete(d, term))
        loaded = ConfigManager.load(tmp_path)
        with pytest.raises(ConfigError, match=f"agreed term '{term}' in game.json"):
            loaded.validate_agreement()

    def test_deleted_whole_block_fails(self, tmp_path):
        _clone_config(tmp_path, mutate=lambda d: _delete(d, "scoring"))
        with pytest.raises(ConfigError, match="agreed term 'scoring.capture_cop'"):
            ConfigManager.load(tmp_path).validate_agreement()

    def test_every_required_term_exists_in_shipped_tree(self, cfg):
        for term in REQUIRED_AGREED_TERMS:
            assert cfg.game(term) is not None

    def test_partner_config_aliases_and_defaults(self, cfg):
        assert cfg.game("pheromones.pheromone_min_center_intensity") == 0.5
        assert cfg.game("pheromones.dialect") == "reference"
        assert cfg.game("crypto.dialect") == "reference"

    def test_partner_v12_game_json_without_min_center_loads(self):
        game = {
            "agreed_between": ["bestteam", "nis-yar1"],
            "board_and_agents": {
                "axis_origin_corner": "top-left",
                "axis_start_index": 0,
                "cop_start": [0, 0],
                "grid_size": 7,
                "num_agents": 2,
                "thief_start": [3, 3],
            },
            "capture": {
                "resolution": "after_moves",
                "stay_counts_as_move": False,
                "swap_is_capture": True,
            },
            "movement_and_barriers": {
                "max_barriers": 14,
                "max_moves": 35,
                "move_set": ["N", "S", "E", "W", "STAY"],
                "seal_barrier_cell": True,
                "survival_threshold": 35,
            },
            "network_and_league": {
                "diversity_reward": 10,
                "max_games_per_team": 10,
                "min_games_to_pass": 2,
                "num_games": 6,
                "response_timeout_sec": 30,
                "token_budget_per_series": 200000,
                "watchdog_timeout_sec": 60,
            },
            "pheromones": {
                "decay_model": "multiplicative",
                "field_includes_current_turn": True,
                "pheromone_center_intensity": 0.9,
                "pheromone_decay": 0.1,
                "pheromone_grid_size": 5,
                "seal_scent_digest": True,
            },
            "rate_limiter_gatekeeper": {
                "concurrent_requests": 2,
                "max_retries": 3,
                "queue_depth": 100,
                "requests_per_minute": 30,
                "retry_backoff_sec": 5,
            },
            "schema_version": "1.2",
            "scoring": {
                "capture_cop": 20,
                "capture_thief": 5,
                "survival_cop": 5,
                "survival_thief": 10,
                "technical_loss": 0,
                "tie_score": 2,
            },
            "version": "1.00",
            "world": {"hint_max_words": 15, "map_area": "New York"},
        }
        loaded = ConfigManager(game_terms=game, private_terms={}, rate_limits={})

        loaded.validate_agreement()
        assert loaded.game("pheromones.pheromone_min_center_intensity") == 0.5
        assert loaded.game("pheromones.dialect") == "reference"
        assert loaded.game("crypto.dialect") == "reference"


class TestNamingAndHash:
    def test_per_game_config_name_zero_padded(self):
        name = ConfigManager.per_game_config_name("nis-yar1-vs-abc-def2", 3)
        assert name == "config_nis-yar1-vs-abc-def2_g03.json"

    def test_per_game_config_name_two_digit(self):
        assert ConfigManager.per_game_config_name("a-vs-b", 12) == "config_a-vs-b_g12.json"

    def test_config_sha256_stable_across_loads(self, cfg):
        digest = cfg.config_sha256()
        assert len(digest) == 64
        assert int(digest, 16) >= 0  # valid hex
        assert ConfigManager.load(POLICE_DIR).config_sha256() == digest

    def test_config_sha256_ignores_json_whitespace(self, tmp_path, cfg):
        _clone_config(tmp_path)  # re-dumped without indentation
        assert ConfigManager.load(tmp_path).config_sha256() == cfg.config_sha256()

    def test_config_sha256_changes_on_value_change(self, tmp_path, cfg):
        def bump(d):
            d["board_and_agents"]["grid_size"] = 9

        _clone_config(tmp_path, mutate=bump)
        assert ConfigManager.load(tmp_path).config_sha256() != cfg.config_sha256()


class TestScentDialectOverride:
    """override_game — the per-opponent runtime scent selector (agreed out-of-band)."""

    def test_swaps_the_scent_dialect(self, tmp_path):
        loaded = ConfigManager.load(_clone_config(tmp_path))
        assert loaded.game("pheromones.dialect") == "reference"  # shipped default (our strength)
        loaded.override_game("pheromones.dialect", "multiplicative_book_v1")
        assert loaded.game("pheromones.dialect") == "multiplicative_book_v1"

    def test_override_leaves_wire_terms_and_uid_untouched(self, tmp_path):
        from pursuit.domain.negotiation import build_terms

        loaded = ConfigManager.load(_clone_config(tmp_path))
        before_terms, before_sha = build_terms(loaded), loaded.config_sha256()
        loaded.override_game("pheromones.dialect", "multiplicative_book_v1")
        assert build_terms(loaded) == before_terms     # dialect is not one of the 14 wire keys
        assert loaded.config_sha256() == before_sha     # so the signed-terms hash / uid is stable

    def test_override_missing_leaf_raises(self, cfg):
        with pytest.raises(ConfigError, match="cannot override"):
            cfg.override_game("pheromones.nonexistent", "book")
