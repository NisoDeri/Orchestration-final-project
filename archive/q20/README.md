# q20 — a "20 Questions" multi-agent league

**Group nis-yar1 (Nissim Deri & Yarden Tziar) · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

Two autonomous agents — a **Judge** and a **Player** — play a "20 Questions" word/association game and compete
in a multi-round inter-group **league**. The Judge picks a paragraph, publishes a hint + an associative-word
chain (`MCP → stream → flow → communication`); the Player fires **20 multiple-choice questions** (4 options) in
one batch, then guesses the paragraph's **opening sentence** and the **associative word**. A deterministic
**referee** scores it. The graded value is the *orchestration* (agents coordinating in NL over MCP), not the raw
outcome.

See [`docs/prd.md`](docs/prd.md) · [`docs/plan.md`](docs/plan.md) · [`docs/todo.md`](docs/todo.md).

## Game rules
One **match** is one Judge vs one Player. The flow (referee = the engine, never an LLM):

| # | Step | Who | What |
|---|------|-----|------|
| 1 | `select` | Judge | Draw a secret paragraph from the corpus (deterministic RNG, **not** the LLM — keeps the truth stable). |
| 2 | `publish` | Judge | Emit only the **public view**: a `hint` + an **associative-word chain** (`MCP → stream → flow → communication`). The paragraph / opening sentence / associative word stay hidden. |
| 3 | `ask` | Player | Fire **20 multiple-choice questions** (4 options each) in **one batch**. |
| 4 | `answer` | Judge | Answer each MCQ with a 0-based option index; never reveals the secret. |
| 5 | `guess` | Player | From hint + chain + answers, guess the **opening sentence** and the **associative word**. |
| 6 | `score` | Referee | Compare guess to the secret and award points. |

**Scoring** (config-driven, `config/setup.json:game.scoring`; provisional per the brief):
the Player **wins** if it gets *both* the opening sentence and the associative word, **ties** if *exactly
one*, **loses** if *neither*. Points: **win 3 · tie 1 · loss 1**; the **Judge always earns +2** for running a
clean round. The single pure function `game/scoring.py:determine_outcome(guess, spec)` encodes the win/tie/loss
rule and is trivial to swap when the official rule is finalized.

**Leak-guard.** Matching is case/whitespace/punctuation-insensitive (Latin **and** Hebrew). Over MCP the Judge's
`reveal` tool is refused until the Player has called `commit_guess`, so the answer cannot leak mid-round.

## Architecture (one line per layer)
```
cli/main.py   thin CLI (play-round | run-league | serve | play-mcp | report) -> SDK only
 └ sdk/sdk.py  the only orchestrator: run_round, run_league, assemble_log
    ├ agents/  judge · player · protocol · factory · fake (FakeJudge/FakePlayer = deterministic, CI-safe)
    ├ game/    corpus · round (state) · scoring (pure, config-driven determine_outcome)
    ├ mcp/     judge_server · player_server · client (FastMCP, lazy-imported)
    └ shared/  config · gatekeeper · cost · ollama_client · logger · exceptions · version
config/  setup.json (game/league/scoring/servers) · models.json · rate_limits.json
data/    corpus.sample.json (bundled; pluggable)
ui/      web standings + round replay (pure client-side)   scripts/ui_server.py  stdlib no-cache server
```
Engine is deterministic; the LLM (local **Ollama**, no API key) lives only at the edges. Every `src/` file is
≤150 lines, ruff-clean (E,F,W,I,N,UP,B,C4,SIM), tests ≥85% coverage. Heavy deps (fastmcp, google) are lazy.

## How to run
```bash
# deterministic round — no model, no network (what CI runs):
uv run q20 play-round --fake          # writes artifacts/round_log.json

# real local models (Ollama running locally):
uv run q20 play-round

# round-robin league skeleton over groups -> artifacts/league.json:
uv run q20 run-league --groups nis-yar1 rival-a rival-b

# inter-group play over MCP: one terminal per server, then play over the wire:
uv run q20 serve judge   # :8765
uv run q20 serve player  # :8766
uv run q20 play-mcp

# re-summarize any saved log:
uv run q20 report artifacts/round_log.json
```

## Web UI — standings + round replay
A pure client-side app (`ui/index.html`, `ui/app.js`, `ui/theme.css`) with two tabs:

- **League standings** — ranked table from `artifacts/league.json` (points, share bar, rank→grade 1st≈100 …
  last≈70) plus the per-round results grid.
- **Round replay** — reads `artifacts/round_log.json`: the Judge's hint + word-chain, all 20 multiple-choice
  questions with the Judge's pick ticked, the Player's guess vs the truth, and the referee's score.

Serve it with the bundled stdlib server (no-cache, forces UTF-8 for the Hebrew project path):
```bash
uv run python scripts/ui_server.py            # opens http://127.0.0.1:8000/ui/index.html
uv run python scripts/ui_server.py --port 9000 --no-open
```
The server roots at the project dir so the page fetches both `ui/` assets and live `artifacts/*.json`. Play a
match in another terminal, then click **⟳ Reload latest**. A bundled `ui/sample_round.json` plays out of the
box; the two **Load JSON** buttons let you open any league/round log by hand. No build step, no dependencies.

## How to join the league
Each group exposes a **Judge** and a **Player** as FastMCP servers (`q20 serve judge|player`); opponents connect
with `q20 play-mcp --judge-url … --player-url …`. Locally that's `127.0.0.1`; for the live cross-group league we
bridge over ngrok/login (same pattern as the HW6 bonus). The MCP tool contract is the shared interface — agree
it early. Scoring, question/option counts, league rounds and role mix (player ~4× / judge ~2×) are all in
[`config/setup.json`](config/setup.json), so rule changes are config edits, not rewrites.

The shared **MCP tool contract** (Judge server / Player server):

| Server | Tool | In | Out |
|--------|------|----|-----|
| Judge | `publish` | — | `{hint, chain}` |
| Judge | `answer` | `{questions:[{text,options}]}` | `{answers:[int]}` |
| Judge | `commit_guess` | — | `{ok:true}` |
| Judge | `reveal` | — | `{revealed, opening_sentence?, associative_word?}` (refused before commit) |
| Player | `ask` | `{view}` | `{questions:[{text,options}]}` |
| Player | `guess` | `{view, qa}` | `{opening_sentence, associative_word}` |

## Config reference (zero hardcoding — every tunable lives here)
All three files are version-checked against the code (`shared/version.py:CODE_VERSION`, currently `1.00`); a
mismatch fails fast at load. There are **no magic numbers in `src/`** — `constants.py` holds only fallbacks.

**`config/setup.json`**
| Key | Meaning |
|-----|---------|
| `project` | group name, authors, repo, course metadata (stamped into every round log). |
| `game.questions` / `game.options` | batch size (20) and options per MCQ (4). |
| `game.seed` | RNG seed for deterministic corpus draws. |
| `game.scoring` | `{win, tie, loss, judge}` points grid (the swappable rule). |
| `game.corpus` | `{source, path}` — `source:"bundled"` reads `path`; pluggable for other sources. |
| `league` | `rounds`, `roles_per_group:{player,judge}`, `pairing` (round-robin). |
| `servers` | `host`, `judge`/`player` ports, optional `live` (use Ollama brains over MCP vs. fakes). |

**`config/models.json`** — `provider`, `ollama_base_url`, and a per-role `agents` map
(`judge`/`player`/`default` each `{model, temperature}`). Judge and Player run **two different** local models so
the dialogue is genuine cross-model communication. **`config/rate_limits.json`** — per-service
`requests_per_minute` / `concurrent_max` / `retry_after_seconds` / `max_retries` enforced by the gatekeeper,
plus `cost.max_cost_usd_per_run` (local Ollama is priced at $0, but the cap is enforced the instant a metered
cloud model is swapped in).

## Vibe-Coding lifecycle
Idea → **PRD** → **Plan** → **TODO** → Verify → Execute → Push, with the three base docs tracked in the repo:
[`docs/initial.md`](docs/initial.md) (idea) → [`docs/prd.md`](docs/prd.md) → [`docs/plan.md`](docs/plan.md) →
[`docs/todo.md`](docs/todo.md). Open rule questions are isolated behind `config/` + the two pure seams
(`scoring.determine_outcome`, `corpus.Corpus`) so finalizing the brief is a config edit, not a rewrite.

## Tests & quality gates
```bash
uv run pytest                 # 121 tests; engine + agents + shared + sessions + CLI
uv run ruff check src tests   # E,F,W,I,N,UP,B,C4,SIM — clean
```
The deterministic `FakeJudge`/`FakePlayer` run the **entire** pipeline (round, league, MCP sessions) with **no
model and no network**, so CI is green offline. Coverage is **~99%** on the measured engine (`cli/`, `mcp/`
transport are integration-tested but omitted from the coverage gate); the threshold is **≥85%**. Every `src/`
file is **≤150 lines**.
