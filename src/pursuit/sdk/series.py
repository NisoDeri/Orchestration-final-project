"""Series driver — N sub-games, role alternation, fresh PeerRuntime each (arch §sdk).

Odd sub-games are played in my CONFIG role, even ones in the opposite role (the
reference's alternation), and every sub-game re-runs the handshake inside its fresh
:class:`PeerRuntime` (INTEROP §4.6). Emission here is the MINIMAL writer: the raw
sealed per-sub-game log (nonces revealed post-audit, replayable) plus one series
summary JSON under ``logs/<group_id>/`` — the full 4-artifact schema-1.1 builders
land in the report stage. ``ScentBelief`` is the stage-2 stand-in belief exposing
exactly the BeliefV2 surface the turn handler and the v1 brains consume.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.constants import Cell, Role
from pursuit.domain.scoring import ScoreTable
from pursuit.exceptions import ConfigError
from pursuit.peer.audit import SubgameOutcome
from pursuit.peer.runtime import PeerRuntime


def _cell_of(key: str) -> Cell:
    row_text, _, col_text = key.partition(",")
    return (int(row_text), int(col_text))


class ScentBelief:
    """Wire-driven stand-in belief: the mode is the opponent's strongest scent cell.

    Duck-types the surface both seams need — ``diffuse``/``observe_smell`` (turn
    handler + lab arena) and ``most_likely``/``most_likely_p`` (v1 brains). BeliefV2
    plugs into the exact same calls when the strategy stage wires it.
    """

    def __init__(self, start: Cell) -> None:
        self._mode: Cell = (int(start[0]), int(start[1]))  # opponent's signed start cell
        self._p = 1.0

    def diffuse(self, opponent_role: Any = None, reference: Any = None) -> None:
        """PREDICT is a no-op here: the scent mode is already the freshest evidence."""

    def observe_smell(self, cells: dict[str, float]) -> None:
        """UPDATE: adopt the strongest cell (ties row-major, like ScentModel.strongest)."""
        if cells:
            key = min(cells, key=lambda k: (-float(cells[k]), _cell_of(k)))
            self._mode, self._p = _cell_of(key), min(1.0, float(cells[key]))

    def most_likely(self) -> Cell:
        return self._mode

    def most_likely_p(self) -> float:
        return self._p


def belief_for(config: Any, role: Role) -> Any:
    """BeliefV2 when private belief config is present; else the ScentBelief stand-in."""
    key = "thief_start" if role is Role.POLICE else "cop_start"
    start: Cell = tuple(config.game(f"board_and_agents.{key}"))  # type: ignore[assignment]
    try:
        cfg = config.private("belief")
    except Exception:  # noqa: BLE001
        return ScentBelief(start)
    if not isinstance(cfg, dict) or "sigma_obs" not in cfg:
        return ScentBelief(start)
    from pursuit.domain.belief.engine import BeliefV2  # import here — keeps lab import-free

    board_size = int(config.game("board_and_agents.grid_size"))
    belief_cfg = {
        "move_set": list(config.game("movement_and_barriers.move_set")),
        **{k: cfg[k] for k in cfg if k != "smell_trust_weight" and k != "hint_trust_prior"},
    }
    scent_cfg = {
        "dialect": config.game("pheromones.dialect"),
        "board_size": board_size,
        "smell_grid_size": int(config.game("pheromones.pheromone_grid_size")),
        "emit_intensity": float(config.game("pheromones.pheromone_center_intensity")),
        "decay_per_step": float(config.game("pheromones.pheromone_decay")),
        "min_center_intensity": float(config.game("pheromones.pheromone_min_center_intensity")),
    }
    return BeliefV2(board_size, belief_cfg, scent_cfg)


def counted_games(config: Any) -> int:
    """The rule-37 ledger count; a fresh ledger (absent key) is 0 (ruling A9b)."""
    try:
        return int(config.private("game.counted_games_so_far"))
    except ConfigError:
        return 0


def run_series(config: Any, role: Role, num_games: int, transport: Any, inboxes: Any, *,
               keypair: tuple[bytes, bytes], brain_factory: Any, sysinfo: dict[str, Any],
               github_commit: str, watchdog: Any = None,
               logs_dir: str | Path | None = None) -> dict[str, Any]:
    """Play ``num_games`` sub-games; aggregate scores + the tie rule; emit logs."""
    my_gid = str(config.private("game.group_id"))
    table = ScoreTable(config.game("scoring"))
    rows: list[dict[str, int]] = []
    subs: list[dict[str, Any]] = []
    game_id = ""
    for number in range(1, num_games + 1):
        inboxes.turns.drain()  # stale-turn hygiene between sub-games (INTEROP §2.4);
        inboxes.audits.drain()  # safe: fresh turns only follow the new handshake
        role_now = role if number % 2 == 1 else role.opponent  # odd = my config role
        runtime = PeerRuntime(role_now, config, transport, inboxes,
                              brain_factory(role_now), belief_for(config, role_now),
                              keypair, sysinfo=sysinfo, github_commit=github_commit,
                              counted_games=counted_games(config), watchdog=watchdog)
        outcome = runtime.run()
        game_id = outcome.game_id
        opp_gid = outcome.opponent_group or "opponent"
        rows.append({my_gid: outcome.scores[role_now],
                     opp_gid: outcome.scores[role_now.opponent]})
        subs.append(_sub_row(number, role_now, my_gid, opp_gid, outcome))
        if logs_dir is not None:
            _write_json(Path(logs_dir) / my_gid / f"log_{game_id}_g{number:02d}.json",
                        _log_document(number, role_now, my_gid, outcome))
    summary = {"game_id": game_id, "group_id": my_gid, "num_sub_games": num_games,
               "sub_games": subs, **table.series_totals(rows)}
    if logs_dir is not None:
        _write_json(Path(logs_dir) / my_gid / f"series_{game_id}.json", summary)
    return summary


def _sub_row(number: int, role: Role, my_gid: str, opp_gid: str,
             outcome: SubgameOutcome) -> dict[str, Any]:
    """One result row (the shape the report-stage result artifact will consume)."""
    return {"sub_game_number": number,
            "roles": {my_gid: role.value, opp_gid: role.opponent.value},
            "result": outcome.result.value,
            "winner_role": None if outcome.winner is None else outcome.winner.value,
            "score": {my_gid: outcome.scores[role], opp_gid: outcome.scores[role.opponent]},
            "steps": outcome.steps, "game_uid": outcome.game_uid,
            "audit": {key: outcome.audit[key] for key in
                      ("passed", "forgery", "opponent_received", "failed_steps")}}


def _log_document(number: int, role: Role, my_gid: str,
                  outcome: SubgameOutcome) -> dict[str, Any]:
    """Minimal replayable per-sub-game log: summary + the revealed sealed chain."""
    return {"summary": {"sub_game_number": number, "group_id": my_gid, "role": role.value,
                        "opponent_group_id": outcome.opponent_group,
                        "game_id": outcome.game_id, "game_uid": outcome.game_uid,
                        "result": outcome.result.value,
                        "winner_role": None if outcome.winner is None else outcome.winner.value,
                        "steps": outcome.steps, "audit": outcome.audit},
            "records": outcome.records}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
