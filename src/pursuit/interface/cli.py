"""pursuit CLI — a thin argparse shell over the SDK (Table-5 gate: rule 3).

Config-only addressing (PRD-5): there are NO port/URL flags — peers are wired
entirely from ``config/<role>/game.toml`` + the signed ``game.json``. The ONLY
game-logic import in this module is :mod:`pursuit.sdk`; a unit test enforces it.

Subcommands::

    peer --role {police,thief} [--config-dir PATH] [--fake-opponent]
    lab  --games N --seed S --police module:Class --thief module:Class
         [--config-dir PATH]

``--fake-opponent`` runs the CI-safe in-process demo (FakeTransport + greedy
reference-baseline opponent) through the exact same SDK path as a league game.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pursuit.exceptions import PursuitError
from pursuit.sdk import run_lab, run_peer

ROLES = ("police", "thief")


def build_parser() -> argparse.ArgumentParser:
    """The full argument grammar; anything outside it is refused by argparse."""
    parser = argparse.ArgumentParser(
        prog="pursuit", description="P2P Cops & Robbers peer — group nis-yar1")
    commands = parser.add_subparsers(dest="command", required=True)
    peer = commands.add_parser("peer", help="run one peer for a full series")
    peer.add_argument("--role", required=True, choices=ROLES,
                      help="which side this OS process plays")
    peer.add_argument("--config-dir", default=None,
                      help="config directory (default: config/<role>)")
    peer.add_argument("--fake-opponent", action="store_true",
                      help="self-contained demo: in-process greedy opponent, no network")
    lab = commands.add_parser("lab", help="paired-seed self-play lab (D7)")
    lab.add_argument("--games", type=int, required=True, help="number of paired seeds")
    lab.add_argument("--seed", type=int, required=True, help="base seed")
    lab.add_argument("--police", required=True, help="police brain 'module:Class'")
    lab.add_argument("--thief", required=True, help="thief brain 'module:Class'")
    lab.add_argument("--config-dir", default=None,
                     help="signed-terms source (default: config/police)")
    return parser


def _config_dir(explicit: str | None, fallback_role: str) -> Path:
    """Config-only addressing: an explicit dir wins, else the repo-layout default."""
    return Path(explicit) if explicit else Path("config") / fallback_role


def main(argv: list[str] | None = None) -> int:
    """Parse, dispatch through the SDK, print the JSON summary; 0 on success."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "peer":
            summary = run_peer(_config_dir(args.config_dir, args.role), args.role,
                               fake_opponent=args.fake_opponent)
        else:
            summary = run_lab(args.games, args.seed, args.police, args.thief,
                              _config_dir(args.config_dir, "police"))
    except PursuitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0
