from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from pursuit.report.consensus import mutual_agreement_signature, settlement


SCHEMA = (
    "Summary and final result for the WHOLE series between two teams: per-sub-game scores "
    "+ aggregate; identity lives in the declaration."
)


def _step0_commit(records: Any) -> str | None:
    for record in records or []:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        try:
            step = int(payload.get("step", -1))
        except Exception:  # noqa: BLE001
            step = -1
        if step == 0 and payload.get("github_commit"):
            return str(payload["github_commit"])
    return None


def _head(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _expand_commit(repo: Path, head: str, commit: str | None) -> str | None:
    if not commit:
        return None
    if len(commit) == 40:
        return commit
    if head.startswith(commit):
        return head
    try:
        return subprocess.check_output(["git", "rev-parse", commit], cwd=repo, text=True).strip()
    except Exception:  # noqa: BLE001
        return commit


def repair(repo: Path, result_path: Path, my_gid: str, opponent_gid: str) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    game_id = str(result["game_id"])
    groups = sorted([opponent_gid, my_gid])
    head = _head(repo)
    config = tomllib.loads((repo / "config/police/game.toml").read_text(encoding="utf-8"))

    repos: dict[str, dict[str, str]] = {my_gid: dict(config["game"]["repos"])}
    counted: dict[str, int] = {my_gid: int(config["game"].get("counted_games_so_far", 0) or 0)}

    for row in result.get("sub_games", []):
        number = int(row["sub_game_number"])
        log_path = repo / f"logs/{my_gid}/log_{game_id}_g{number:02d}.json"
        log = json.loads(log_path.read_text(encoding="utf-8"))
        summary = log.get("summary", {})
        opponent_identity = summary.get("opponent_identity") or {}
        if opponent_identity.get("repos"):
            repos[opponent_gid] = dict(opponent_identity["repos"])
        counted[opponent_gid] = int(
            opponent_identity.get(
                "counted_games_played",
                opponent_identity.get("counted_games_so_far", counted.get(opponent_gid, 0)),
            )
            or 0
        )

        my_role = str(summary.get("role"))
        opponent_role = "police" if my_role == "thief" else "thief"
        by_role = {
            my_role: _expand_commit(repo, head, _step0_commit(log.get("records"))),
            opponent_role: _expand_commit(
                repo, head, _step0_commit((summary.get("audit") or {}).get("their_records"))
            ),
        }
        row["roles"] = {gid: row.get("roles", {})[gid] for gid in groups if gid in row.get("roles", {})}
        row["github_commit"] = {
            gid: by_role[row["roles"][gid]]
            for gid in groups
            if row.get("roles", {}).get(gid) in by_role and by_role[row["roles"][gid]]
        }
        row["tokens"] = {gid: row.get("tokens", {}).get(gid, 0) for gid in groups}
        row["score"] = {gid: row.get("score", {}).get(gid, 0) for gid in groups}

    result["_schema"] = SCHEMA
    result["links"] = {
        "declaration": f"declaration_{game_id}.json",
        "config": f"config_{game_id}_g<NN>.json",
        "log": f"log_{game_id}_g<NN>.json",
        "result": f"result_{game_id}.json",
        "github": {gid: repos[gid] for gid in groups if gid in repos},
    }
    result["groups"] = groups
    final = result.setdefault("final_result", {})
    for key in ("total_score", "sub_games_won", "tokens_total_series"):
        if isinstance(final.get(key), dict):
            final[key] = {gid: final[key].get(gid, 0) for gid in groups}
    final["games_played_including_this"] = {gid: counted.get(gid, 0) for gid in groups}
    final["first_meeting_between_groups"] = True
    final["diversity_reward_applied"] = {gid: False for gid in groups}
    result.setdefault("mutual_agreement", {})["confirmed"] = all(
        (row.get("audit") or {}).get("log_verified") for row in result.get("sub_games", [])
    )
    result["mutual_agreement"]["sha256"] = mutual_agreement_signature(result)
    result["settlement"] = settlement(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--result", default="logs/nis-yar1/result_anrbj666-vs-nis-yar1.json")
    parser.add_argument("--my-gid", default="nis-yar1")
    parser.add_argument("--opponent-gid", default="anrbj666")
    parser.add_argument("--copy-to", default="artifacts/result_anrbj666-vs-nis-yar1.corrected-1715.json")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    result_path = (repo / args.result).resolve()
    original = json.loads(result_path.read_text(encoding="utf-8"))
    backup = repo / "artifacts/result_anrbj666-vs-nis-yar1.before-format-fix-1715.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")

    repaired = repair(repo, result_path, args.my_gid, args.opponent_gid)
    blob = json.dumps(repaired, ensure_ascii=False, indent=2)
    result_path.write_text(blob, encoding="utf-8")
    copy_to = (repo / args.copy_to).resolve()
    copy_to.parent.mkdir(parents=True, exist_ok=True)
    copy_to.write_text(blob, encoding="utf-8")
    print(result_path)
    print(copy_to)
    print(repaired["links"]["github"])
    print(repaired["sub_games"][0]["github_commit"])


if __name__ == "__main__":
    main()
