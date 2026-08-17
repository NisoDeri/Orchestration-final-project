"""Append-only live step stream for the two fixed-role peer processes.

This monitor is deliberately read-only. It tails the ConsoleProgress output files,
prints the existing step history once, and then prints each new step as it arrives.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _progress_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("game=") or stripped.startswith("=== Friendly game")


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _emit(role: str, lines: list[str]) -> None:
    for line in lines:
        if _progress_line(line):
            print(f"[{role.upper():6}] {line.strip()}", flush=True)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Tail every live game step from both peers")
    parser.add_argument("--thief-log", type=Path, required=True)
    parser.add_argument("--cop-log", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()

    sources = {"thief": args.thief_log, "cop": args.cop_log}
    seen: dict[str, int] = {role: 0 for role in sources}

    print("nis-yar1 live step stream")
    print("Every turn from both role processes will appear below. Ctrl+C stops only this view.\n")

    while True:
        for role, path in sources.items():
            lines = _read_lines(path)
            if len(lines) < seen[role]:
                seen[role] = 0
            new_lines = lines[seen[role]:]
            _emit(role, new_lines)
            seen[role] = len(lines)
        time.sleep(max(0.05, args.interval))


if __name__ == "__main__":
    main()
