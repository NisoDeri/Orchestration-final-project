# features.md — prioritized MAX-GRADE feature/extension backlog for `q20`

**Group nis-yar1 · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

> Goal: reach **rank-1 ≈ 100** and max out the explicitly-scored **creativity / out-of-the-box** axis without
> breaking any hard rule (`q20` package · ≤150-line files · ruff clean · pytest ≥85% · deterministic engine,
> LLM at edges · injected `FakeJudge`/`FakePlayer` · lazy heavy deps · zero hardcoded params · local Ollama).
> Each item lists **Impact** (grade lift), **Effort**, **Gate** (build-now vs needs-confirmed-rules),
> **Reuse** (what HW6 code adapts), and a concrete **Implementation** sketch with file targets under `src/q20/`.

Legend — Impact: ★ small · ★★ solid · ★★★ rank-mover. Effort: S (<½ day) · M (1 day) · L (2-3 days).
Gate: **NOW** = safe to build against current stubs/config · **RULES** = needs confirmed game rules ·
**LEAGUE** = needs the inter-group handshake/dataset agreed.

---

## Tier 0 — must-ship (these turn a 60 into a defensible high score; do first)

### 0.1 Deterministic end-to-end pipeline with injected fakes  ★★★ · S · NOW
The single most-scored thing in our HW history: a full Judge↔Player↔Referee round that runs with **no model,
no network**. Already in the plan — finish it first so every later feature has a CI-safe harness.
- **Reuse:** `hw6/.../agents/fake.py`, `agents/factory.py`, `sdk/sdk.py:run_round`.
- **Impl:** `agents/fake.py` (`FakeJudge.select/answer`, `FakePlayer.ask/guess` from a seeded RNG),
  `sdk/sdk.py:run_round(judge, player, corpus, cfg)`; `q20 play-round --fake` exits 0 with a scored log.
- **Tests:** failing→passing on `scoring.determine_outcome` (all of win/tie/loss + judge+2) and a full-round
  integration test asserting a deterministic `Outcome` from a fixed seed.

### 0.2 Leak-guard / answer-isolation test suite  ★★★ · S · NOW
A Judge that leaks the opening sentence or associative word inside the hint/chain/answers is both a rules
violation and a credibility win when demonstrated. Property-style tests assert the published payload never
contains the secret.
- **Impl:** `game/round.py` keeps `RoundSpec.secret` (opening_sentence, associative_word, paragraph) separate
  from `RoundSpec.public` (hint, chain). A pure `game/leakguard.py:assert_no_leak(public, secret)` (substring +
  normalized-token + lemma-ish overlap check). The MCP judge server only ever serializes `.public`.
- **Tests:** fuzz 200 seeded rounds → `assert_no_leak` holds; a deliberately-leaky `FakeJudge` variant must
  be caught (proves the guard has teeth).

### 0.3 Schema-validated MCP tool contract + protocol versioning  ★★ · S · LEAGUE
Inter-group play dies on contract drift. Pin a versioned JSON contract for the 4 message types
(`publish`, `ask`, `answer`, `guess`) and validate on both ends.
- **Reuse:** `hw6/.../mcp/client.py`, `mcp/cross.py`, `shared/version.py`.
- **Impl:** `mcp/contract.py` with dataclasses + a `validate(payload, kind)`; `shared/version.PROTOCOL = "q20/1"`
  echoed in every envelope; reject mismatched majors with a typed `ProtocolError` (extend `shared/exceptions`).

---

## Tier 1 — high-impact, build NOW (rank-movers that don't need final rules)

### 1.1 League standings + round-replay web UI  ★★★ · M · NOW (polish later)
Biggest visible-creativity payoff; we already own a working board-replay UI. Standings table + a step-through
replay of any match (hint → 20 Q/A → guesses → score), reading the same JSON logs the engine writes.
- **Reuse:** `hw6/ui/{index.html,live.html,app.js,theme.css,sample_game_log.json}` — swap the Monopoly board
  renderer for a "transcript" renderer; keep the timeline scrubber, theming, and live-poll loop.
- **Impl:** `q20 serve` (static-serve `ui/` + emit `ui/league.json` and `ui/round/<id>.json` from
  `sdk.assemble_log`). Two views: `standings.html` (sortable table: rank, pts, W/T/L, as-player vs as-judge)
  and `replay.html` (question-by-question reveal with the chosen MCQ option highlighted, secret revealed only
  at the end). Add a Gemini-prompted hero/trophy asset to match our house style.
- **Gate:** schema is stable now; only cosmetic tweaks once final scoring lands.

### 1.2 Analytics: information-gain per question + win-rate dashboard  ★★★ · M · NOW
Directly differentiates us and feeds 1.3/1.4. Compute, per question, the **expected information gain** (entropy
reduction over the player's candidate-paragraph distribution) and surface it.
- **Impl:** `analytics/infogain.py` (pure): given a candidate-belief distribution and an answered MCQ, compute
  `H(before) - E[H(after)]`. `analytics/stats.py`: win-rate, avg guesses-correct, judge-fairness, points/round,
  rolling by opponent. Output `ui/analytics.json` for the dashboard; CLI `q20 report --analytics`.
- **Reuse:** `hw6/.../game/belief.py` (decode-to-belief pattern) and `report/reporter.py`.
- **Tests:** infogain on hand-built distributions (a perfectly-splitting question = max gain; a useless one = 0).

### 1.3 Self-play tuning harness for question selection  ★★★ · L · NOW (tunes; rules refine reward)
The strongest *player-quality* lever — and pure orchestration craft. Run thousands of `FakePlayer`/heuristic
rounds offline to pick the 20 questions that maximize expected info-gain / expected score.
- **Impl:** `tuning/selfplay.py` (deterministic loop over seeds, all params from `config/tuning.json`:
  population size, candidate question bank size, objective weights). `tuning/optimizer.py`: greedy/beam selection
  of a 20-question set maximizing cumulative `infogain` (reuse 1.2) under a no-redundancy penalty. Emits
  `config/question_bank.tuned.json` consumed by the real player — **zero hardcoding**, just a regenerated config.
- **Gate:** runs now against the provisional reward; when scoring is finalized, only the objective weights in
  `config/tuning.json` change. Keep it CI-cheap (tiny default budget; full runs are an opt-in flag).
- **Tests:** optimizer is deterministic per seed; tuned set strictly beats a random set on the offline objective.

### 1.4 ELO / Glicko ratings alongside league points  ★★ · S · NOW
Cheap, high-signal, and shows depth beyond the brief's raw points. Per-group rating updated each match;
separate **as-player** and **as-judge** ratings (judge skill = how often it produces fair, non-trivial rounds).
- **Impl:** `analytics/elo.py` (pure `update(rating_a, rating_b, score) -> (new_a, new_b)`, K from config).
  Fold into standings UI as a secondary sort. **Does not replace** the official points → no rules risk.
- **Tests:** symmetry, monotonicity, and a fixed multi-match sequence → known ratings.

### 1.5 Observability: structured run logs + cost/latency ledger  ★★ · S · NOW
Professional-bar signal and a debugging multiplier. Every LLM call and round step emits a structured event;
a per-match ledger tracks tokens, wall-time, retries, and (local) cost = $0 — proving the no-API-key claim.
- **Reuse:** `hw6/.../shared/{logger.py,cost.py,gatekeeper.py}` almost verbatim.
- **Impl:** `shared/logger.py` JSON-lines events (`round_id`, `phase`, `agent`, `latency_ms`, `tokens`);
  `shared/cost.py` aggregates into the match log; surface a "match cost/latency" panel in the UI.

### 1.6 Pluggable corpus + corpus linter  ★★ · M · NOW
De-risks the unknown dataset and is itself a feature. `Corpus` interface with multiple backends + a linter that
rejects paragraphs unsuitable for the game (too short, no clean opening sentence, leaks trivially).
- **Impl:** `game/corpus.py:Corpus.sample()` with backends `JsonCorpus` (bundled `data/corpus.sample.json`),
  `WikipediaCorpus`, `ArxivCorpus`, `TextDirCorpus` — selected by `config/setup.json:corpus.source`,
  heavy fetchers **lazy-imported**. `game/corpus_lint.py:check(paragraph)` enforces min-length, sentence
  segmentation, and an associative-word existence heuristic.
- **Tests:** linter rejects pathological paragraphs; `JsonCorpus.sample(seed)` is reproducible.

---

## Tier 2 — high creativity, low risk (build NOW, great demo value)

### 2.1 Commentary / caster agent  ★★ · M · NOW
A third, non-scoring LLM agent that narrates each match ("Player gambled on a low-info question 7 — paid off!")
using the analytics from 1.2. Pure flair, strong in a live demo, zero impact on the deterministic engine.
- **Impl:** `agents/commentator.py` consuming the round log + infogain; output a `commentary[]` array in the
  log that the replay UI (1.1) renders as a side panel. Gatekept Ollama call, lazy, behind `--commentary`.
- **Tests:** with the LLM stubbed, the commentary builder produces one line per phase deterministically.

### 2.2 Strategy profiles / "personas" for the Player  ★★ · S · NOW
Swappable question-selection strategies — `aggressive` (max info-gain), `safe` (cover broad categories),
`adaptive` (re-rank after the chain). All driven by `config/strategies.json`; lets the tuning harness (1.3)
compare them and the UI label which persona played.
- **Impl:** `agents/strategy.py` with a registry; `player.py` selects via config. Strategies are pure functions
  over the candidate bank → trivially unit-tested and CI-safe.

### 2.3 Adversarial / robustness test pack  ★★ · S · NOW
Beyond leak-guard (0.2): malformed opponent payloads, fewer/more than 4 options, duplicate questions, empty
chain, judge that always answers "A", non-UTF8/Hebrew text. Proves the referee + contract are bulletproof —
exactly the robustness Dr. Segal scrutinizes.
- **Impl:** parametrized tests against `mcp/contract.validate` and `sdk.run_round`; each bad input → typed
  exception or a defined forfeit, never a crash.

### 2.4 Match reproducibility / replay-from-seed  ★ · S · NOW
Any match fully reconstructible from `{seed, config_hash, corpus_id, protocol_version}` stored in the log.
Pure determinism dividend; also a fairness/audit feature for the league.
- **Impl:** `sdk.assemble_log` records the tuple; `q20 play-round --replay <log>` reruns and asserts byte-equal
  outcome. **Tests:** replay of a stored log reproduces the exact `Outcome`.

---

## Tier 3 — needs confirmed RULES (scaffold the seams now, fill on confirmation)

### 3.1 Final scoring rule  ★★★ · S · RULES
Swap the single pure function when rules land — already isolated by design.
- **Impl:** `game/scoring.py:determine_outcome(guess, spec, cfg)` reads `config/setup.json:scoring`; only the
  body + config grid change. Add a regression test per confirmed example the lecturer gives.

### 3.2 MCQ-correctness scoring (if answers are graded)  ★★ · S · RULES
The brief's open question: are the judge's 20 answers themselves scored, or only the final guesses? Keep a
config flag `scoring.grade_answers`; if enabled, the referee also scores answer correctness against `secret`.
- **Impl:** branch lives entirely in `scoring.py` + config; no engine reshape.

### 3.3 Real LLM Judge/Player prompts  ★★★ · L · RULES
The language brain. Prompt the judge to emit hint+chain+answers and the player to emit MCQs+guesses, decoded
to typed structures. **Local Ollama (qwen2.5 / aya), no API key.**
- **Reuse:** `hw6/.../agents/{brain.py,protocol.py}`, `shared/ollama_client.py`, decode-to-belief pattern.
- **Impl:** `agents/protocol.py` (prompt templates from `config/prompts.json`) + `agents/{judge,player}.py`
  thin wrappers; strict decode with a deterministic fallback so a model hiccup degrades to a `FakeJudge`-style
  default rather than crashing a league match. Gate the prompt format on the confirmed rules.

---

## Tier 4 — needs LEAGUE logistics agreed (high payoff, external dependency)

### 4.1 Inter-group MCP bridge (live league)  ★★★ · M · LEAGUE
Connect our agents to another group's over MCP — the spiritual core of the course and a proven win for us
(HW6 bonus, played live). Build against our own two servers now; flip to remote when the handshake is agreed.
- **Reuse:** `hw6/.../mcp/{cross.py,client.py,orchestrator.py}` (ngrok/login bridge) almost directly.
- **Impl:** `mcp/judge_server.py` + `mcp/player_server.py` (FastMCP, lazy), `mcp/bridge.py` adapting `cross.py`;
  connection params (`url`, `transport`, `token`) in `config/servers.json`. A `--local` mode runs both servers
  in one process for CI/dev.

### 4.2 League scheduler + auto-run + email digest  ★★ · M · LEAGUE
Round-robin pairing honoring "≈4× player / ≈2× judge", auto-running matches and emailing a standings digest —
reusing our working Gmail path.
- **Reuse:** `hw6/.../report/{reporter.py,mailer.py}`, `tools/google_auth.py` (lazy `google` import).
- **Impl:** `game/league.py:schedule(groups, cfg)` (pure, fully tested) + `sdk.run_league`; `q20 run-league
  --email` sends the digest. **Tests:** schedule satisfies the per-group role counts for N in {3,4,6,8}.

### 4.3 Fairness / anti-collusion audit  ★ · S · LEAGUE
Detect a judge feeding an unfair (trivially-guessable or impossible) round, or a player/judge pair colluding.
Flags rounds with anomalous info-gain or guess-accuracy in the standings UI.
- **Impl:** `analytics/audit.py` (pure) over match logs using 1.2 metrics; thresholds in config.

---

## Suggested build order (max grade per unit effort)

1. **Tier 0** in full (0.1 → 0.2 → 0.3) — the deterministic, leak-safe, contract-validated core.
2. **1.1 (UI) + 1.5 (observability) + 1.6 (corpus)** — visible professionalism + de-risk the dataset.
3. **1.2 (analytics) → 1.3 (self-play tuning) → 1.4 (ELO)** — the player-quality + creativity differentiators.
4. **Tier 2 (2.1–2.4)** — cheap creativity/robustness that demos beautifully.
5. **3.1/3.2 the moment rules land**, then **3.3 (LLM brains)**.
6. **Tier 4** once league logistics are confirmed (4.1 first — it's the course's headline).

**Rule-independence guarantee:** every NOW item lives behind `config/*.json` + the two seams
(`scoring.determine_outcome`, `Corpus`), so confirmed rules slot in as config + one-function edits — never a
rewrite. This lets us bank ~80% of the grade-moving work before the brief is finalized.
