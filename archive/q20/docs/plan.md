# plan.md — execution strategy & architecture for `q20`

Derived from [`prd.md`](prd.md). Plan-mode output (Vibe-Coding step 2). Modular so finalized rules drop in.

## Architecture (layers)
```
cli/main.py            thin CLI (play-round | run-league | serve | report)  -> SDK only
  └─ sdk/sdk.py        the ONLY orchestrator: run_round, run_league, assemble_log
       ├─ agents/      judge.py · player.py · protocol.py · factory.py · fake.py
       │                 (LLM brains; FakeJudge/FakePlayer = deterministic, for tests/CI)
       ├─ game/        corpus.py · round.py (state) · scoring.py (pure, config-driven)
       ├─ mcp/         judge_server.py · player_server.py · client.py (FastMCP, lazy)
       └─ shared/      config · gatekeeper · cost · ollama_client · logger · exceptions · version
config/                setup.json (game/league/scoring/servers) · models.json · rate_limits.json
data/                  corpus.sample.json (bundled); real corpus pluggable
tests/                 unit/ + integration/ ;  .github/workflows/ci.yml
```

## Design principles
- **Pure engine, LLM at the edges.** Scoring/round-state/league are deterministic + unit-tested; the LLM only
  writes language (questions, hints, association reasoning, guesses). (Direct HW6 lesson — it's what scored.)
- **Zero hardcoding.** Every tunable (grid of scoring, #questions=20, #options=4, league rounds, models,
  corpus source) lives in `config/`. Rule changes = config edits.
- **Swappable rules behind interfaces.** `game/scoring.py:determine_outcome(guess, spec, cfg)` and
  `game/corpus.py:Corpus` are the two seams most likely to change; both are tiny + isolated.
- **Injected agents.** `run_round(judge, player, ...)` takes any object with the agent protocol → a
  deterministic `FakeJudge`/`FakePlayer` proves the pipeline with no model/network (CI-safe).
- **Transport-agnostic.** Same agents run in-process (dev/tests) or over **MCP** (league). Reuse HW6's bridge.
- **≤150-line files, ruff, pytest ≥85%, lazy heavy imports, gatekept LLM calls.**

## Build phases (mirrors todo.md)
1. **Scaffold** — pyproject, config, shared layer, constants, CI, README, .env-example. *(this pass)*
2. **Engine** — `Corpus`, `RoundSpec`/round state, `scoring.determine_outcome` + unit tests. *(this pass, stub rules)*
3. **Agents** — Judge/Player protocol + `FakeJudge`/`FakePlayer`; in-process `run_round` end-to-end. *(this pass)*
4. **LLM brains** — real Ollama-backed judge/player prompts (`protocol.py`) — **after rules confirmed**.
5. **League** — `run_league`, standings, role rotation (4× player / 2× judge). *(skeleton this pass)*
6. **MCP** — judge/player servers + client; inter-group bridge (ngrok/login) — reuse HW6.
7. **UI** — web standings + round replay (stretch; reuse HW6 UI).
8. **Harden** — coverage ≥85%, ruff, ≤150 lines, docs, granular commits, push.

## What's runnable after this pass
`q20 play-round --fake` plays a full Judge-vs-Player round on the bundled sample corpus with deterministic
agents, scores it via the referee, and prints/writes a round log — verifying the whole architecture before any
LLM or finalized rule is wired. Real models + confirmed rules then slot into the existing seams.

## Verification
Failing→passing tests for scoring + round flow; `q20 play-round --fake` exits 0 with a scored log; ruff clean;
≥85% coverage on the engine; every `src/` file ≤150 lines; CI green.

## Open decisions (tracked in initial.md §Open questions) — do NOT block the scaffold
corpus source · exact outcome rule · league pairing · inter-group MCP handshake · deadline.
