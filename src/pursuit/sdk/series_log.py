"""Log/document emission helpers for the series driver (arch §sdk).

The MINIMAL writer surface pulled out of :mod:`pursuit.sdk.series`: the report-row
shape (:func:`sub_row`), the replayable sealed per-sub-game log document
(:func:`log_document`) and the JSON sink (:func:`write_json`). Kept pure — no game
parameters are hardcoded here; everything is derived from the passed ``outcome``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.constants import Role
from pursuit.peer.audit import SubgameOutcome


def sub_row(number: int, role: Role, my_gid: str, opp_gid: str,
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


def log_document(number: int, role: Role, my_gid: str,
                 outcome: SubgameOutcome) -> dict[str, Any]:
    """Minimal replayable per-sub-game log: summary + the revealed sealed chain."""
    return {"summary": {"sub_game_number": number, "group_id": my_gid, "role": role.value,
                        "opponent_group_id": outcome.opponent_group,
                        "game_id": outcome.game_id, "game_uid": outcome.game_uid,
                        "result": outcome.result.value,
                        "winner_role": None if outcome.winner is None else outcome.winner.value,
                        "steps": outcome.steps, "audit": outcome.audit},
            "records": outcome.records}


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Emit ``data`` as pretty UTF-8 JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
