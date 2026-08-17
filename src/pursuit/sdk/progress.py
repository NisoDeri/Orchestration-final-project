"""Human-readable progress output for live peer runs.

Progress is local-only and is never included in a wire message or sealed payload.
"""

from __future__ import annotations

import sys
from typing import Any


class ConsoleProgress:
    """Print one compact line whenever a peer completes or receives a turn."""

    def __init__(self, max_steps: int = 35, stream: Any = None) -> None:
        self.max_steps = int(max_steps)
        self.stream = stream or sys.stdout
        self._last_game: int | None = None

    def __call__(self, snapshot: dict[str, Any]) -> None:
        game = snapshot.get("sub_game_number", "?")
        if game != self._last_game:
            print(f"\n=== Friendly game {game} started ===", file=self.stream, flush=True)
            self._last_game = game
        status = snapshot.get("status", "unknown")
        step = int(snapshot.get("step", 0))
        role = snapshot.get("role", "?")
        print(f"game={game} role={role} status={status} step={step}/{self.max_steps}",
              file=self.stream, flush=True)

    def game_finished(self, sub_game: int | None, outcome: Any) -> None:
        game = sub_game if sub_game is not None else "?"
        result = getattr(outcome, "result", "unknown")
        steps = getattr(outcome, "steps", "?")
        print(f"game={game} finished result={result} steps={steps}/{self.max_steps}",
              file=self.stream, flush=True)
