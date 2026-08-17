"""Live-ish friendly monitor for the fixed-role peer setup.

Shows the pieces that matter during a scheduled friendly:
ports, recent tunnel/peer logs, HTTP reachability, and per-sub-game artifacts.
It is intentionally read-only; it never starts/stops peers or edits artifacts.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping


DEFAULT_GAME_ID = "anrbj666-vs-nis-yar1"
DEFAULT_URLS = (
    "https://duckling-judgingly-frigidly.ngrok-free.dev/",
    "https://duckling-judgingly-frigidly.ngrok-free.dev/cop/mcp",
    "https://duckling-judgingly-frigidly.ngrok-free.dev/thief/mcp",
)


def _run(command: list[str], timeout: float = 5.0) -> str:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def _probe(url: str, timeout: float = 4.0) -> str:
    req = urllib.request.Request(url, method="GET", headers={"user-agent": "nis-yar1-monitor"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")
    except OSError:
        return "-"


def _tail(path: Path, lines: int = 4) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return text[-lines:]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _launch_logs(tunnel_dir: Path) -> list[Path]:
    log_dir = tunnel_dir / "logs"
    return sorted(log_dir.glob("friendly-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)


def _ports() -> list[str]:
    lines: list[str] = []
    for port, service in ((8799, "path proxy"), (8801, "thief"), (8802, "cop")):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                lines.append(f"127.0.0.1:{port} LISTENING ({service})")
        except OSError:
            lines.append(f"127.0.0.1:{port} DOWN ({service})")
    return lines


def _task(task_name: str) -> list[str]:
    text = _run(["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST"])
    keep = []
    for line in text.splitlines():
        if line.startswith(("TaskName:", "Next Run Time:", "Status:", "Last Run Time:", "Last Result:")):
            keep.append(line)
    return keep or [text or f"{task_name}: task not found"]


def _is_current(path: Path, since: datetime | None) -> bool:
    return since is None or datetime.fromtimestamp(path.stat().st_mtime) >= since


def _winner_group(summary: Mapping[str, Any]) -> str | None:
    winner = summary.get("winner_role")
    if winner is None:
        return None
    my_gid = str(summary.get("group_id", "nis-yar1"))
    opp_gid = str(summary.get("opponent_group_id", "anrbj666"))
    my_role = str(summary.get("role", ""))
    return my_gid if winner == my_role else opp_gid


def _score(summary: Mapping[str, Any]) -> dict[str, int]:
    my_gid = str(summary.get("group_id", "nis-yar1"))
    opp_gid = str(summary.get("opponent_group_id", "anrbj666"))
    my_role = str(summary.get("role", ""))
    opp_role = "thief" if my_role == "police" else "police"
    result = str(summary.get("result", ""))
    if result == "capture":
        cop_gid = my_gid if my_role == "police" else opp_gid
        thief_gid = my_gid if my_role == "thief" else opp_gid
        return {cop_gid: 20, thief_gid: 5}
    if result == "survival":
        thief_gid = my_gid if my_role == "thief" else opp_gid if opp_role == "thief" else my_gid
        cop_gid = my_gid if my_role == "police" else opp_gid
        return {thief_gid: 10, cop_gid: 5}
    if result == "tie":
        return {my_gid: 2, opp_gid: 2}
    return {my_gid: 0, opp_gid: 0}


def _current_summaries(log_dir: Path, game_id: str,
                       since: datetime | None) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(log_dir.glob(f"log_{game_id}_g*.json")):
        if not _is_current(path, since):
            continue
        data = _load_json(path) or {}
        summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
        if summary:
            rows.append((path, summary))
    return sorted(rows, key=lambda item: int(item[1].get("sub_game_number", 0) or 0))


def _game_status(log_dir: Path, game_id: str, opponent_group: str,
                 since: datetime | None) -> list[str]:
    rows = _current_summaries(log_dir, game_id, since)
    groups = ("nis-yar1", opponent_group)
    totals = {gid: 0 for gid in groups}
    wins = {gid: 0 for gid in groups}
    for _path, summary in rows:
        for gid, points in _score(summary).items():
            totals[gid] = totals.get(gid, 0) + int(points)
        winner = _winner_group(summary)
        if winner:
            wins[winner] = wins.get(winner, 0) + 1
    completed = {int(summary.get("sub_game_number", 0) or 0) for _path, summary in rows}
    next_game = next((n for n in range(1, 7) if n not in completed), None)
    lines = [
        f"current friendly: completed {len(completed)}/6 | "
        f"score nis-yar1:{totals.get('nis-yar1', 0)} "
        f"{opponent_group}:{totals.get(opponent_group, 0)} | "
        f"wins nis-yar1:{wins.get('nis-yar1', 0)} "
        f"{opponent_group}:{wins.get(opponent_group, 0)}",
        f"now: {'series complete' if next_game is None else f'waiting/playing g{next_game:02d}'}",
    ]
    return lines


def _result_rows(log_dir: Path, game_id: str, opponent_group: str,
                 since: datetime | None) -> list[str]:
    rows: list[str] = []
    for path in sorted(log_dir.glob(f"log_{game_id}_g*.json")):
        data = _load_json(path) or {}
        summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        marker = "NEW" if _is_current(path, since) else "old"
        audit = summary.get("audit", {}) if isinstance(summary.get("audit"), dict) else {}
        score = _score(summary)
        winner = _winner_group(summary) or "-"
        rows.append(
            f"{marker:3} g{int(summary.get('sub_game_number', 0) or 0):02d} "
            f"{summary.get('role', '?'):6} {summary.get('result', 'running?'):14} "
            f"winner={winner} score={score.get('nis-yar1', 0)}-"
            f"{score.get(opponent_group, 0)} "
            f"steps={summary.get('steps', '-')} turns={summary.get('turns_completed', '-')} "
            f"audit={audit.get('passed', '-')} mtime={mtime.strftime('%H:%M:%S')}"
        )
    return rows


def _latest_role_file(tunnel_dir: Path, role: str, suffix: str) -> Path | None:
    candidates = list(tunnel_dir.glob(f"*{role}.{suffix}"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _live_progress(tunnel_dir: Path) -> list[str]:
    """Return the latest ConsoleProgress events from both fixed-role peers."""
    lines: list[str] = []
    for role in ("thief", "cop"):
        path = _latest_role_file(tunnel_dir, role, "out")
        if path is None:
            lines.append(f"{role:5}: no output file")
            continue
        events = [line.strip() for line in _tail(path, 120)
                  if "game=" in line or "Friendly game" in line]
        state = events[-1] if events else "waiting for handshake/first turn"
        lines.append(f"{role:5}: {state}  [{path.name}, {_mtime(path)}]")
    return lines


def _artifact_summary(log_dir: Path, game_id: str) -> list[str]:
    lines: list[str] = []
    for name in (f"series_{game_id}.json", f"result_{game_id}.json"):
        path = log_dir / name
        data = _load_json(path)
        if not data:
            lines.append(f"{name}: missing")
            continue
        rows = data.get("sub_games", [])
        totals = data.get("totals") or data.get("final_result", {}).get("total_score")
        lines.append(f"{name}: rows={len(rows)} totals={totals} mtime={_mtime(path)}")
    return lines


def render(repo: Path, game_id: str, opponent_group: str, since: datetime | None,
           urls: tuple[str, ...], task_name: str | None) -> str:
    tunnel_dir = repo / ".tunnels"
    game_log_dir = repo / "logs" / "nis-yar1"
    out: list[str] = []
    out.append(f"nis-yar1 friendly monitor | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"repo: {repo}")
    if since:
        out.append(f"marking NEW artifacts since: {since.strftime('%Y-%m-%d %H:%M:%S')}")
    out.append("")

    out.append("Game Status")
    out.extend(f"  {line}" for line in _game_status(
        game_log_dir, game_id, opponent_group, since))
    out.append("")

    out.append("Live Role Progress")
    out.extend(f"  {line}" for line in _live_progress(tunnel_dir))
    out.append("")

    if task_name:
        out.append("Scheduled Task")
        out.extend(f"  {line}" for line in _task(task_name))
        out.append("")

    out.append("Ports")
    ports = _ports()
    out.extend(f"  {line}" for line in ports) if ports else out.append("  no 8799/8801/8802 listeners")
    out.append("")

    if urls:
        out.append("HTTP Probes")
        for url in urls:
            out.append(f"  {url} -> {_probe(url)}")
        out.append("")

    out.append("Latest Launcher")
    launches = _launch_logs(tunnel_dir)
    if launches:
        latest = launches[0]
        out.append(f"  {latest.name} mtime={_mtime(latest)}")
        out.extend(f"    {line}" for line in _tail(latest, 8))
    else:
        out.append("  no launcher logs")
    out.append("")

    out.append("Peer/Tunnel Files")
    peer_files = [path for role in ("thief", "cop") for suffix in ("err", "out")
                  if (path := _latest_role_file(tunnel_dir, role, suffix)) is not None]
    for path in peer_files:
        name = path.name
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        out.append(f"  {name:16} size={size:7} mtime={_mtime(path)}")
        if exists and size:
            out.extend(f"    {line}" for line in _tail(path, 3))
    out.append("")

    out.append("Sub-Games")
    rows = _result_rows(game_log_dir, game_id, opponent_group, since)
    out.extend(f"  {row}" for row in rows) if rows else out.append("  no sub-game logs yet")
    out.append("")

    out.append("Artifacts")
    out.extend(f"  {line}" for line in _artifact_summary(game_log_dir, game_id))
    return "\n".join(out)


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    today = datetime.now().date()
    for fmt, text in (("%Y-%m-%d %H:%M:%S", value), ("%Y-%m-%d %H:%M", f"{today} {value}")):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise SystemExit("bad --since; use HH:MM or YYYY-MM-DD HH:MM:SS")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path.cwd()))
    parser.add_argument("--game-id", default=DEFAULT_GAME_ID)
    parser.add_argument("--opponent-group", default=None)
    parser.add_argument("--since", default=None, help="mark logs newer than HH:MM as NEW")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--task-name", default=None)
    parser.add_argument("--url", action="append", default=[],
                        help="optional endpoint to probe (repeatable; disabled by default)")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    since = _parse_since(args.since)
    opponent_group = args.opponent_group
    if not opponent_group:
        pair = args.game_id.split("-vs-", 1)
        opponent_group = pair[1] if len(pair) == 2 and pair[0] == "nis-yar1" else pair[0]
    while True:
        if not args.once:
            print("\033[2J\033[H", end="")
        print("=" * 100)
        print(render(repo, args.game_id, opponent_group, since,
                     tuple(args.url), args.task_name))
        if args.once:
            break
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
