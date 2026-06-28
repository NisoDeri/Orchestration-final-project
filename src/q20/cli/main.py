"""Thin CLI: orchestrate via the SDK only — no business logic lives here.

Subcommands:
  play-round  -- play ONE Judge-vs-Player round (``--fake`` = deterministic, no model)
  run-league  -- play the round-robin league skeleton over configured groups
  serve       -- start one MCP server (judge | player) for inter-group league play
  play-mcp    -- play ONE round OVER THE WIRE against running judge+player servers
  report      -- re-render a compact summary from an existing JSON round log
"""

import argparse
import json
from pathlib import Path

from q20.agents.factory import fake_agents, live_agents
from q20.constants import Role
from q20.game.corpus import load_corpus
from q20.sdk.sdk import get_report, run_league, run_round
from q20.shared.config import ConfigLoader

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _ROOT / "config"


def _write_log(log: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "round_log.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _play_round(args) -> None:
    cfg = ConfigLoader(_CONFIG_DIR).load()
    corpus = load_corpus(cfg, _ROOT)
    agents = (fake_agents(cfg) if args.fake
              else live_agents(cfg, ConfigLoader.build_gatekeeper(cfg), corpus))
    log = run_round(agents[Role.JUDGE.value], agents[Role.PLAYER.value], corpus, cfg)
    path = _write_log(log, Path(args.out or "artifacts"))
    summary = get_report(log)
    print(json.dumps(summary, indent=2, ensure_ascii=False))  # noqa: T201
    print(f"round complete; outcome={log['outcome']}; wrote {path}")  # noqa: T201


def _run_league(args) -> None:
    cfg = ConfigLoader(_CONFIG_DIR).load()
    corpus = load_corpus(cfg, _ROOT)
    groups = args.groups or [cfg.setup["project"].get("group", "us"), "rival-a", "rival-b"]

    def make(gid, role):  # injected-agents seam (in-process today; MCP later)
        if gid == "corpus":
            return corpus
        return fake_agents(cfg)[role.value]

    result = run_league(cfg, groups, make)
    print(json.dumps(result["standings"], indent=2, ensure_ascii=False))  # noqa: T201
    out = Path(args.out or "artifacts")
    out.mkdir(parents=True, exist_ok=True)
    (out / "league.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    print(f"league complete; ranking={result['ranking']}")  # noqa: T201


def _serve(args) -> None:
    if args.which == "judge":
        from q20.mcp.judge_server import main as srv
    else:
        from q20.mcp.player_server import main as srv
    srv()


def _play_mcp(args) -> None:
    import logging

    from q20.mcp.client import play_over_mcp
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = ConfigLoader(_CONFIG_DIR).load()
    s = cfg.setup["servers"]
    judge_url = args.judge_url or f"http://{s['host']}:{s['judge']}/mcp"
    player_url = args.player_url or f"http://{s['host']}:{s['player']}/mcp"
    log = play_over_mcp(cfg, judge_url, player_url)
    path = _write_log(log, Path(args.out or "artifacts"))
    print(json.dumps(get_report(log), indent=2, ensure_ascii=False))  # noqa: T201
    print(f"wire round complete; outcome={log['outcome']}; wrote {path}")  # noqa: T201


def _report(args) -> None:
    log = json.loads(Path(args.json).read_text(encoding="utf-8"))
    print(json.dumps(get_report(log), indent=2, ensure_ascii=False))  # noqa: T201


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="q20")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("play-round", help="play one Judge-vs-Player round")
    pr.add_argument("--fake", action="store_true", help="deterministic agents (CI / no-GPU)")
    pr.add_argument("--out", default=None, help="output directory for the round log")
    pr.set_defaults(func=_play_round)
    lg = sub.add_parser("run-league", help="play the round-robin league skeleton")
    lg.add_argument("--groups", nargs="*", help="group ids (default: us + two rivals)")
    lg.add_argument("--out", default=None)
    lg.set_defaults(func=_run_league)
    sv = sub.add_parser("serve", help="start an MCP server for inter-group league play")
    sv.add_argument("which", choices=["judge", "player"])
    sv.set_defaults(func=_serve)
    pm = sub.add_parser("play-mcp", help="play one round over the wire vs running servers")
    pm.add_argument("--judge-url", default=None, help="judge server URL (default: config)")
    pm.add_argument("--player-url", default=None, help="player server URL (default: config)")
    pm.add_argument("--out", default=None)
    pm.set_defaults(func=_play_mcp)
    rp = sub.add_parser("report", help="summarize an existing round log")
    rp.add_argument("json")
    rp.set_defaults(func=_report)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
