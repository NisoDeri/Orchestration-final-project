#!/usr/bin/env python3
"""Brain fitness evaluator — the constant-validation harness for cop/thief improvement.

A candidate is BETTER iff it beats the current baseline of its role in paired-seed play
(the opponent role held fixed), WITHOUT regressing against the greedy reference baseline.

    uv run python scripts/fitness.py cop   pursuit.strategy.police:MyPoliceV2   [games] [seed]
    uv run python scripts/fitness.py thief pursuit.strategy.thief:MyThiefV2     [games] [seed]

Prints JSON: {"role","vs_baseline","vs_greedy","verdict"} where vs_baseline>0.5 means the
candidate outplays the current shipped brain, and verdict=="PROMOTE" when it strictly wins
vs baseline and does not regress (>=~0.97) vs greedy. Deterministic for a fixed (games,seed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pursuit.sdk.lab_gate import run_lab_versus  # noqa: E402

BASELINE_POLICE = "pursuit.strategy.police:InterceptorPoliceBrain"
BASELINE_THIEF = "pursuit.strategy.thief:SurvivorThiefBrain"
GREEDY_POLICE = "pursuit.strategy.greedy:GreedyPoliceBrain"
GREEDY_THIEF = "pursuit.strategy.greedy:GreedyThiefBrain"
CONFIG_DIR = "config/police"


def _rate(police_a: str, thief_a: str, police_b: str, thief_b: str,
          games: int, seed: int) -> float:
    result = run_lab_versus(games, seed, police_a, thief_a, police_b, thief_b, CONFIG_DIR)
    return round(float(result["win_rate_A"]), 4)


def evaluate(role: str, candidate: str, games: int, seed: int) -> dict:
    """Candidate-vs-baseline and candidate-vs-greedy, opponent role held fixed."""
    if role == "cop":  # vary the police; thief fixed = Survivor both sides
        vs_baseline = _rate(candidate, BASELINE_THIEF, BASELINE_POLICE, BASELINE_THIEF, games, seed)
        vs_greedy = _rate(candidate, BASELINE_THIEF, GREEDY_POLICE, BASELINE_THIEF, games, seed)
    elif role == "thief":  # vary the thief; police fixed = Interceptor both sides
        bp = BASELINE_POLICE
        vs_baseline = _rate(bp, candidate, bp, BASELINE_THIEF, games, seed)
        vs_greedy = _rate(bp, candidate, bp, GREEDY_THIEF, games, seed)
    else:
        raise SystemExit(f"role must be 'cop' or 'thief', got {role!r}")
    verdict = "PROMOTE" if (vs_baseline > 0.5 and vs_greedy >= 0.97) else "keep-baseline"
    return {"role": role, "candidate": candidate, "games": games * 2, "seed": seed,
            "vs_baseline": vs_baseline, "vs_greedy": vs_greedy, "verdict": verdict}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    role, candidate = argv[1], argv[2]
    games = int(argv[3]) if len(argv) > 3 else 100
    seed = int(argv[4]) if len(argv) > 4 else 42
    print(json.dumps(evaluate(role, candidate, games, seed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
