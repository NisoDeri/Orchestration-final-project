# First Blood — Self-Play Lab Results (D7)

**Date:** 2026-07-14  
**Group:** nis-yar1  
**Seed:** 42 | **Games per matchup:** 100

## Board Configuration

| Parameter | Value |
|-----------|-------|
| Grid size | 7x7 |
| Cop start | (0,0) — top-left corner |
| Thief start | (3,3) — centre |
| Survival threshold | 35 thief moves |
| Max cop moves | 35 |
| Max barriers | 14 |

Initial BFS distance cop→thief: **6 cells**.

## Self-Play Results (100 games each, seed 42)

| Matchup | Police Brain | Thief Brain | Police Wins | Thief Wins | Avg Steps |
|---------|-------------|------------|-------------|------------|-----------|
| 1 | InterceptorPoliceBrain | SurvivorThiefBrain | 0 (0%) | 100 (100%) | 35.0 |
| 2 | InterceptorPoliceBrain | GreedyThiefBrain | 0 (0%) | 100 (100%) | 35.0 |
| 3 | GreedyPoliceBrain | SurvivorThiefBrain | 0 (0%) | 100 (100%) | 35.0 |

**Finding:** With the current signed game parameters (cop starts at corner [0,0],
thief at centre [3,3], BFS gap = 6, survival threshold = 35), the thief always
reaches the step quota before the cop can close the distance. This reflects the
intended league balance — in a symmetric league both sides alternate roles so
neither has a persistent advantage.

## Belief Entropy Convergence (5 games, InterceptorPoliceBrain)

The police's BeliefV2 starts with **5.615 bits** (uniform prior over 49 cells).
After the **first scent observation** (sigma_obs = 0.1, very sharp), entropy
drops to **0.0 bits** — the belief perfectly localises the thief.
Brief spikes (~0.35 bits) appear when the thief moves away between consecutive
observations; the belief re-converges within one additional turn.

**Key insight:** BeliefV2 achieves near-perfect localisation within 1 step
using scent alone (sigma_obs = 0.1). The bottleneck is not information quality
but the physical distance the cop must close.

## Strategy Comparison

| Dimension | InterceptorPoliceBrain | GreedyPoliceBrain |
|-----------|----------------------|-------------------|
| Distance metric | BFS true distance | Manhattan (barrier-blind) |
| Barrier doctrine | Deterministic value-test | 15% coin flip on own-step cell |
| Self-walling risk | Structurally impossible (W4 fix) | Present (reference weakness W4) |
| Tie-break | Mobility-weighted | Move-set order |

| Dimension | SurvivorThiefBrain | GreedyThiefBrain |
|-----------|-------------------|-----------------|
| Score function | BFS flee + mobility bonus | Manhattan flee + unvisited preference |
| Jail-risk ban | Active when cop has charges | None |
| Barrier awareness | Full (charges observable) | None |
