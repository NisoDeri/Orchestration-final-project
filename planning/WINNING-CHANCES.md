# League winning-chances assessment (group nis-yar1)

Synthesis of a multi-dimension adversarial review (correctness, interop, security, quality)
against honest, reproduced evidence. Verdict grounded in artifacts, not optimism.

## Verdict: GOOD vs the pod, competitive vs a strong peer

Against a **reference-derived opponent** (what most of the 4-pair pod will run), our chances are
**strong**. Against a **peer as good as us**, a 6-sub-game series becomes a coin-flip decided by
marginal cop skill + our lie-detection edge — we are competitive, not dominant.

### Why we win vs a reference peer
Evidence (paired-seed lab, BeliefV2, reproducible): our brains beat the reference greedy baseline
**win-rate 0.975–0.98** (p < 1e-21) over 80–200 games; a **mirror match is 0.50** (balanced, the
correct sanity result). Real **2-process MCP play** completed a full series with all audits passing.

- **As cop vs their thief:** under the reference scent dialect the opponent's cell is the belief
  argmax, so BeliefV2 localizes near-perfectly; our interceptor does barrier-aware BFS true-distance
  pursuit and now prefers the **universally-honored landing capture** (review fix) over a
  barrier-on-thief a reference peer would reject. We capture their (weaker) thief.
- **As thief vs their cop:** mobility-maximizing flight + hard jail-risk ban survives the reference
  cop's min-Manhattan chase + 15% barrier coin. We survive to 35.
- Roles **alternate** (3 cop / 3 thief per series), so the cop-start handicap ([0,0] vs [3,3]) is
  symmetric — the series is decided by *whose cop is better*, and ours is.

### Where we are vulnerable (honest)
1. **A peer as strong as us → mirror 0.50.** Evenly-matched teams tie on raw play; the series tips
   on marginal cop capture-rate and the lie-detection edge (below).
2. **The opponent lie-profiler is dormant.** `strategy/profiler.py` is unit-tested but opponent
   hint/intent records are not yet surfaced into `SubgameOutcome`, so cross-sub-game profiling —
   our flagship graded mechanic the reference lacks — does not yet fire in a real game.
3. **Ed25519 verification is fail-open by necessity.** A peer that omits its pubkey skips the
   step-0 signature check (reference peers don't sign). Accepted interop tradeoff, documented.

### Confirmed defects — FIXED before this assessment
- **CRITICAL (integrity):** commit-reveal was not bound to the live wire commits — an opponent
  could reveal a different move than it committed after seeing ours. Fixed: per-turn commits are
  retained and `revealed==live` is asserted at audit; a move-swap is now provable forgery (0/0).
- **HIGH (win-rate):** the police preferred a barrier-on-thief finisher over a landing capture;
  reference peers reject rule-46 barrier capture, so we were *wasting captures vs the pod*. Fixed.
- **MEDIUM (interop):** `config_sha256` hashed the full game.json, not the 14 agreed terms — the
  mutual-agreement SHA could never match a reference partner (report mismatch = 0/0). Fixed.
- **MEDIUM (robustness):** the mandatory audit only ran on Deadline/Transport errors; any other
  crash skipped settlement. Fixed (any mid-game exception → 0/0 with audit still run).
- **LOW:** default dialect was still `book` — a partial crypto block could fall back to a form the
  pod doesn't use. Fixed to `reference`.

## Legal improvements, ranked (impact × effort) — before league week

| # | Change | Module | Expected effect | Effort |
|---|--------|--------|-----------------|--------|
| 1 | **Surface opponent revealed records** into `SubgameOutcome`, activate the profiler | `peer/audit.py`, `sdk/series.py` | Turns on cross-game lie-detection — the graded Integrity/Adaptation edge + real win value vs lying peers | Medium |
| 2 | **Deeper cop pursuit + multi-step barrier cages** (predict flight, quadrant seal) | `strategy/police.py` | Raises cop capture-rate vs a *competent* thief — tips the mirror in our favour, the series-decider | Medium–High |
| 3 | **Validate + enable the thief scent-decoy** (currently default-off) via a lab ablation | `strategy/thief.py`, `strategy/decoy.py` | If the lab shows it beats plain flight, it degrades the opponent's belief map — more thief survivals | Medium |
| 4 | **Emit result.json as canonical bytes** (not pretty-printed) | `infra/email.py` | Avoids a report-identity deduction (SPEC §6) | Low |
| 5 | **Ollama gauntlet** — pick the banter/interpreter model at p95 ≤ 8s | lab experiment | Better forensic hint interpretation (feeds #1); pure upside, 0 mandatory tokens | Low–Medium |
| 6 | Screenshots (live heatmap + replay "Verified OK"), self-score | manual | Mandatory deliverables + code-quality points | Low |

**Biggest single lever for *winning more*:** #2 (a stronger cop) — it converts mirror-tie series
into wins. **Biggest lever for *grade*:** #1 (activate lie-detection) — it lights up the flagship
mechanic the reference simulator entirely lacks.

## Bottom line
The system runs end-to-end today, is byte-exact interoperable, and beats the reference baseline
decisively. Against the pod we should score clean wins; against a strong peer we are a coin-flip we
can tip with #1 and #2. Nothing outstanding voids a match. Recommended pre-league order: 1 → 2 → 5 → 3.
