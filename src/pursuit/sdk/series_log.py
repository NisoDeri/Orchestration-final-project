"""Log/document emission for the series driver (arch §sdk): the report-row :func:`sub_row`,
the replayable :func:`log_document`, the :func:`write_json` sink and :func:`emit_artifacts`.
No game params hardcoded — all derived from the passed ``outcome``/``config``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.constants import GameResult, Role
from pursuit.domain.scoring import ScoreTable
from pursuit.peer.audit import SubgameOutcome
from pursuit.strategy.profiler import OpponentProfiler


class LieProfiler:
    """E2 cross-sub-game lie-profiler bridge — gated, non-fatal. Off unless private
    ``strategy.profile_opponent`` is truthy (``None`` on any build error). :meth:`observe`
    folds each sub-game's revealed opponent records into :attr:`prior` — the Beta r_0 the
    next sub-game seeds via :meth:`belief_cfg`; wrapped so it never crashes.
    """

    def __init__(self, config: Any) -> None:
        self.prior: float | None = None
        self._profiler = self._build(config)

    @staticmethod
    def _build(config: Any) -> OpponentProfiler | None:
        try:
            if not bool(config.private("strategy.profile_opponent")):
                return None
            belief = config.private("belief")
            r0 = float(belief.get("hint_trust_prior", 0.5))
            strength = float(belief.get("hint_prior_strength", 2.0))
            moves = list(config.game("movement_and_barriers.move_set"))
            return OpponentProfiler({"hint_alpha0": max(1e-6, r0 * strength),
                                     "hint_beta0": max(1e-6, (1.0 - r0) * strength),
                                     "move_set": moves})
        except Exception:  # noqa: BLE001 — a best-effort creativity hook is never fatal
            return None

    def observe(self, outcome: SubgameOutcome, opponent_role: Role) -> None:
        """Fold the opponent's revealed records; refresh :attr:`prior` for the next sub-game."""
        if self._profiler is None:
            return
        try:
            self._profiler.ingest_subgame(outcome.audit.get("their_records") or [],
                                          opponent_role.value)
            self.prior = self._profiler.trust_prior()
        except Exception:  # noqa: BLE001 — a malformed transcript must never crash the series
            pass

    @staticmethod
    def belief_cfg(config: Any, cfg: dict[str, Any], trust_prior: float | None) -> dict[str, Any]:
        """BeliefV2 cfg with r_0 seeded from a cross-sub-game profile (else the config value)."""
        prior = trust_prior if trust_prior is not None else cfg.get("hint_trust_prior")
        return {"move_set": list(config.game("movement_and_barriers.move_set")),
                "hint_trust_prior": prior,
                **{k: cfg[k] for k in cfg if k not in ("smell_trust_weight", "hint_trust_prior")}}


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


def _opponent(summary: dict[str, Any], my_gid: str) -> str:
    return next((g for g in summary.get("totals", {}) if g != my_gid), "opponent")


def _log_number(doc: dict[str, Any]) -> int:
    return int(doc.get("summary", {}).get("sub_game_number", 0) or 0)


def _read_sibling_logs(out_dir: Path, game_id: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in out_dir.glob(f"log_{game_id}_g*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                docs.append(data)
        except Exception:  # noqa: BLE001 - a corrupt side artifact must not stop reporting
            pass
    return docs


def _role(value: Any) -> Role | None:
    try:
        return Role(value)
    except Exception:  # noqa: BLE001
        return None


def _row_from_log(config: Any, doc: dict[str, Any], my_gid: str, opp_gid: str) -> dict[str, Any]:
    summary = dict(doc.get("summary", {}))
    role = _role(summary.get("role")) or Role.POLICE
    opponent = str(summary.get("opponent_group_id") or opp_gid)
    winner = _role(summary.get("winner_role"))
    result = summary.get("result")
    try:
        game_result = GameResult(result)
    except Exception:  # noqa: BLE001
        game_result = str(result or GameResult.TECHNICAL_LOSS.value)
    by_role = ScoreTable(config.game("scoring")).score_subgame(game_result, winner)
    return {
        "sub_game_number": _log_number(doc),
        "roles": {my_gid: role.value, opponent: role.opponent.value},
        "result": str(result or GameResult.TECHNICAL_LOSS.value),
        "winner_role": None if winner is None else winner.value,
        "score": {my_gid: by_role[role], opponent: by_role[role.opponent]},
        "steps": int(summary.get("steps", 0) or 0),
        "game_uid": str(summary.get("game_uid", "")),
        "audit": {
            "passed": bool((summary.get("audit") or {}).get("passed", False)),
            "forgery": bool((summary.get("audit") or {}).get("forgery", False)),
            "opponent_received": bool((summary.get("audit") or {}).get("opponent_received", False)),
            "failed_steps": list((summary.get("audit") or {}).get("failed_steps", [])),
        },
    }


def _merged_summary(config: Any, summary: dict[str, Any], logs: list[dict[str, Any]],
                    out_dir: Path, my_gid: str, opp_gid: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = str(summary.get("game_id", ""))
    by_number = {_log_number(doc): doc for doc in _read_sibling_logs(out_dir, game_id)}
    by_number.update({_log_number(doc): doc for doc in logs})
    merged_logs = [by_number[n] for n in sorted(by_number) if n > 0]
    if len(merged_logs) <= len(logs):
        return summary, logs
    rows = [_row_from_log(config, doc, my_gid, opp_gid) for doc in merged_logs]
    scores = [dict(row.get("score", {})) for row in rows]
    return {
        **summary,
        "num_sub_games": len(rows),
        "sub_games": rows,
        **ScoreTable(config.game("scoring")).series_totals(scores),
    }, merged_logs


def emit_artifacts(config: Any, summary: dict[str, Any], logs: list[dict[str, Any]],
                   sysinfo: dict[str, Any], github_commit: str,
                   keypair: tuple[bytes, bytes], out_dir: Path) -> list[str]:
    """Build + write the FOUR artifacts; best-effort, never aborts a finished series."""
    import base64

    from pursuit.domain.negotiation import build_terms
    from pursuit.report.artifacts import (
        build_config_artifact,
        build_declaration,
        build_log_artifact,
        build_result_artifact,
        write_artifacts,
    )
    try:
        my_gid = str(summary.get("group_id", ""))
        try:
            counted = int(config.private("game.counted_games_so_far"))
        except Exception:  # noqa: BLE001
            counted = 0
        opp = _opponent(summary, my_gid)
        summary, logs = _merged_summary(config, summary, logs, out_dir, my_gid, opp)
        result = build_result_artifact(summary, my_gid, opp)
        game_id, game_uid = result["game_id"], result["game_uid"]
        subs = list(summary.get("sub_games", []))
        declaration = build_declaration(
            sysinfo, my_gid, config.private("game.members"), github_commit, counted,
            base64.b64encode(keypair[1]).decode("ascii"), config.private("game.repos"),
            opp, game_id, game_uid, len(subs))
        sha, terms = config.config_sha256(), build_terms(config)
        configs = [build_config_artifact(sha, terms, game_id, game_uid,
                                         int(sub.get("sub_game_number", i + 1)))
                   for i, sub in enumerate(subs)]
        log_arts = [build_log_artifact(doc) for doc in logs]
        paths = write_artifacts(out_dir, declaration, configs, result, log_arts)
        maybe_email(config, summary, result)
        return paths
    except Exception:  # noqa: BLE001 — reporting must never crash a completed series
        return []


def maybe_email(config: Any, summary: dict[str, Any], result: dict[str, Any]) -> None:
    """Opt-in (private ``email.enabled``): send the result artifact via the email Gatekeeper."""
    try:
        if not bool(config.private("email.enabled")):
            return
        from pursuit.infra.email import GmailSender
        from pursuit.infra.gatekeeper import Gatekeeper

        subject = f"pursuit result {summary.get('game_id', '')}"
        Gatekeeper.from_config(config, "email").execute(
            GmailSender().send_result, subject, result)  # result = the canonical artifact dict
    except Exception:  # noqa: BLE001 — a send failure must NEVER crash the series
        pass
