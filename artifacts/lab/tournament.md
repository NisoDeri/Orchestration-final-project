# Tournament — do we have smart players?

Our full agent (InterceptorPoliceBrain + herding, SurvivorThiefBrain, BeliefV2, live hint
fusion) vs a **diverse** opponent roster — not just the greedy baseline. 50 paired seeds each
(100 sub-games, role-alternating), `win_rate` and points from A's perspective (A = us).

| Opponent | win_rate (A=us) | points (us / them) | reading |
|---|---|---|---|
| **Greedy** (the reference model) | **0.98** | 1490 / 530 | we dominate the archetype most of the pod runs |
| **Random** (sanity floor) | **1.00** | 1500 / 500 | perfect vs a legal-random agent |
| **Ambush+WallHugger** (a *distinct* chaser + fleer) | **1.00** | 1500 / 500 | not overfit to greedy — we crush a different playstyle too |
| **Ourselves** (strong control) | **0.50** | 1250 / 1250 | only an *identical* copy holds us even |

## Verdict: **yes — genuinely smart, not baseline-lucky.**

The signature of a strong agent is exactly this shape: it **beats a random floor and a distinct
heuristic archetype 100%**, beats the reference model ~98%, and is held even **only by a copy of
itself**. If our brains merely exploited one greedy quirk they would stumble against the
corner-ambush cop / wall-hugger thief — instead they win every game (1500/500). The herding cop
punishes edge-hugging; the mobility-maximizing thief refuses the corners the ambush cop herds toward.

## Honest caveat
The 0.50 vs ourselves means an opponent *as strong as us* would tie on raw play, and such a series
tips on cop-skill margin + our lie-detection edge (which the reference sim wholly lacks). No simple
archetype reaches that level — but a top student pair might, so the last edges (deeper cage play,
the now-live hint fusion) matter at the top of the table.

*Reproduce:* `uv run python scripts/fitness.py` primitives, or the tournament snippet over
`pursuit.strategy.archetypes`. Opponents are lab-only (`src/pursuit/strategy/archetypes.py`).
