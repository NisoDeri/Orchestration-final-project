# todo.md — granular task list for `q20` (20 Questions multi-agent league)

**Group nis-yar1 · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

Vibe-Coding step 3. Derived from [`prd.md`](prd.md), [`plan.md`](plan.md), [`features.md`](features.md),
[`strategy_player.md`](strategy_player.md), [`strategy_judge.md`](strategy_judge.md). Tasks are short and
imperative; check off as you go. Every PRD/feature "you must" maps to tasks here. Hard rules echoed inline as
gates: package `q20` · `[tool.uv] package=false` + `PYTHONPATH=src` · every `src/` `.py` ≤150 lines · ruff
clean (E,F,W,I,N,UP,B,C4,SIM) · pytest ≥85% coverage · deterministic engine, LLM at edges · injected
`FakeJudge`/`FakePlayer` (no model/network for CI) · heavy deps (fastmcp, google) lazy-imported · zero
hardcoded params (all in `config/*.json`) · local Ollama / no API key.

Legend for gates inline: `[NOW]` build immediately · `[RULES]` needs confirmed game rules · `[LEAGUE]` needs
inter-group handshake/dataset.

---

## Phase 0 — Repo Scaffold & Project Hygiene

- [ ] Create repo root `final_project/` and confirm absolute path is the working dir.
- [ ] Create `src/q20/` package directory.
- [ ] Add `src/q20/__init__.py` exporting the package version string.
- [ ] Add `src/q20/__main__.py` delegating to `cli.main:main`.
- [ ] Create `src/q20/shared/` package dir + `__init__.py`.
- [ ] Create `src/q20/game/` package dir + `__init__.py`.
- [ ] Create `src/q20/agents/` package dir + `__init__.py`.
- [ ] Create `src/q20/sdk/` package dir + `__init__.py`.
- [ ] Create `src/q20/cli/` package dir + `__init__.py`.
- [ ] Create `src/q20/mcp/` package dir + `__init__.py`.
- [ ] Create `src/q20/analytics/` package dir + `__init__.py`.
- [ ] Create `src/q20/tuning/` package dir + `__init__.py`.
- [ ] Create `src/q20/tools/` package dir + `__init__.py`.
- [ ] Create `src/q20/report/` package dir + `__init__.py`.
- [ ] Create `config/` directory at repo root.
- [ ] Create `data/` directory at repo root.
- [ ] Create `tests/` dir with `__init__.py`.
- [ ] Create `tests/unit/` dir with `__init__.py`.
- [ ] Create `tests/integration/` dir with `__init__.py`.
- [ ] Create `ui/` directory at repo root.
- [ ] Create `.github/workflows/` directory.
- [ ] Copy HW6 `pyproject.toml` as the starting template.
- [ ] Set `[project].name = "q20"` in `pyproject.toml`.
- [ ] Set `[project].version = "0.1.0"`.
- [ ] Write `[project].description` for the 20-Questions league.
- [ ] Set `requires-python = ">=3.11"`.
- [ ] List `fastmcp` as a dependency (lazy-imported in code).
- [ ] List `google-api-python-client` + auth deps for the email digest (lazy-imported).
- [ ] Add `[dependency-groups].dev`: pytest, pytest-cov, ruff.
- [ ] Set `[tool.uv] package = false` with the Hebrew-path comment.
- [ ] Set `[tool.ruff] line-length = 100`, `target-version = "py311"`.
- [ ] Set `[tool.ruff.lint] select = ["E","F","W","I","N","UP","B","C4","SIM"]`.
- [ ] Decide ruff `ignore` policy (mirror HW6 `E501` only if line-length enforced elsewhere).
- [ ] Set `[tool.pytest.ini_options] testpaths=["tests"]`, `pythonpath=["src"]`.
- [ ] Set pytest `addopts` with `--cov=q20 --cov-report=term-missing --cov-fail-under=85`.
- [ ] Set `[tool.coverage.run] source=["src"]` and `omit` CLI/`__main__`/tools/server-entry modules.
- [ ] Set `[tool.coverage.report] fail_under = 85`.
- [ ] Add `[project.scripts] q20 = "q20.cli.main:main"`.
- [ ] Create `.gitignore` (`.venv`, `__pycache__`, `*.pyc`, `secrets/`, `ui/round/`, `*.log`, coverage files).
- [ ] Create `.env.example` documenting Ollama host + optional Gmail vars (no secrets committed).
- [ ] Add `secrets/.gitkeep` and ensure `secrets/` is gitignored.
- [ ] Create `README.md` stub (title, one-line pitch, badges placeholder).
- [ ] Create `LICENSE` (course-appropriate; e.g. MIT or "academic use").
- [ ] Copy HW6 `.github/workflows/ci.yml` and rename coverage target to `q20`.
- [ ] Update CI `ruff check src tests` step.
- [ ] Update CI pytest step to run `uv run pytest`.
- [ ] Add a CI step asserting every `src/**/*.py` is ≤150 lines (script in `scripts/check_line_limit.py`).
- [ ] Write `scripts/check_line_limit.py` (pure, exits non-zero listing offenders).
- [ ] Add a unit test for `check_line_limit` against a fixture file.
- [ ] Verify `uv sync --dev` succeeds locally with the Hebrew path.
- [ ] Verify `PYTHONPATH=src` import of `q20` works (no editable install).
- [ ] Add a `Makefile`/`tasks.ps1` with `lint`, `test`, `play`, `serve` shortcuts.
- [ ] Commit: "scaffold: q20 package skeleton, pyproject, CI, line-limit gate".

## Phase 1 — Shared Layer (adapt HW6 `shared/`)

- [ ] Adapt `shared/version.py` from HW6; define `__version__`.
- [ ] Add `PROTOCOL = "q20/1"` constant in `shared/version.py`.
- [ ] Add `protocol_major(version)` helper to extract the major for compat checks.
- [ ] Unit-test `protocol_major` for `"q20/1"`, `"q20/2"`, malformed input.
- [ ] Adapt `shared/exceptions.py`; keep base `Q20Error`.
- [ ] Add `ConfigError(Q20Error)` for bad/missing config.
- [ ] Add `LeakError(Q20Error)` for leak-guard violations.
- [ ] Add `ProtocolError(Q20Error)` for contract/version mismatch.
- [ ] Add `GatekeeperError(Q20Error)` for sanitization failures.
- [ ] Add `OllamaError(Q20Error)` for model-call failures.
- [ ] Add `CorpusError(Q20Error)` for corpus loading/lint failures.
- [ ] Unit-test each exception is raisable and subclasses `Q20Error`.
- [ ] Adapt `shared/config.py` loader: read JSON from `config/` by name.
- [ ] Make config path resolution relative to repo root (env override `Q20_CONFIG_DIR`).
- [ ] Add `load(name)` returning a parsed dict; raise `ConfigError` on missing/invalid JSON.
- [ ] Add `get(cfg, "a.b.c", default)` dotted-path accessor (zero-hardcoding helper).
- [ ] Add config caching with an explicit `clear_cache()` for tests.
- [ ] Add `config_hash(cfg)` (stable sha256 of canonical JSON) for reproducibility logs.
- [ ] Unit-test `load`, dotted `get`, missing-key default, `config_hash` stability.
- [ ] Unit-test `load` raises `ConfigError` on a malformed JSON fixture.
- [ ] Adapt `shared/logger.py`: JSON-lines structured events.
- [ ] Define event fields: `ts`, `round_id`, `phase`, `agent`, `level`, `msg`, extras.
- [ ] Add `get_logger(name)` returning a configured logger.
- [ ] Add a `log_event(**fields)` helper writing one JSON line.
- [ ] Make log sink configurable (stdout vs file) via `config`.
- [ ] Unit-test a logged event parses back to the expected dict.
- [ ] Adapt `shared/cost.py`: per-call token/latency/cost ledger (local cost = $0).
- [ ] Add `Ledger.record(tokens, latency_ms, model)` and `Ledger.summary()`.
- [ ] Assert local cost stays `$0` to back the "no API key" claim.
- [ ] Unit-test ledger aggregation (sum tokens, max latency, count, $0 total).
- [ ] Adapt `shared/ollama_client.py`: lazy `import` of the Ollama client.
- [ ] Add `chat(model, messages, **opts)` with a shot-clock timeout from config.
- [ ] Add graceful failure → raise `OllamaError` (caught by gatekeeper → fallback).
- [ ] Add optional `embed(model, text)` for embedding re-rank (graceful if absent).
- [ ] Add a `available()` probe that returns False without raising when Ollama is down.
- [ ] Unit-test `chat`/`embed` with a stubbed client (no network) — assert lazy import.
- [ ] Adapt `shared/gatekeeper.py`: validate/sanitize every LLM output before it leaves an agent.
- [ ] Add `wrap_call(fn, fallback, shot_clock)` running an LLM fn with a deterministic fallback.
- [ ] Add `enforce_schema(payload, model)` (Pydantic, `extra="forbid"`).
- [ ] Add a hook point for the leak-guard scan on outbound Judge payloads.
- [ ] Unit-test gatekeeper falls back deterministically on `OllamaError`/timeout/malformed JSON.
- [ ] Unit-test gatekeeper rejects extra fields (`extra="forbid"`).
- [ ] Create `constants.py` (only true constants: phase names, role names; NOT tunables).
- [ ] Document the "constants vs config" rule at the top of `constants.py`.
- [ ] Verify all shared modules ≤150 lines; split if needed (e.g. `config_paths.py`).
- [ ] Commit: "shared: config/logger/cost/ollama/gatekeeper/version/exceptions adapted from HW6".

## Phase 2 — Config Files (zero hardcoding)

- [ ] Create `config/setup.json` skeleton with top-level keys: `game`, `scoring`, `league`, `judge`,
      `player`, `corpus`, `servers`.
- [ ] `game.n_questions = 20`, `game.n_options = 4` (configurable, not hardcoded).
- [ ] `game.phases = ["select","publish","ask","answer","guess","score"]`.
- [ ] `scoring.win`, `scoring.tie`, `scoring.loss`, `scoring.judge_per_match` (defaults 3/1/1/2) `[RULES]`.
- [ ] `scoring.grade_answers` flag (default false) for MCQ-correctness scoring `[RULES]`.
- [ ] `scoring.outcome_rule` selector (default "both_one_none") `[RULES]`.
- [ ] `league.rounds`, `league.player_games_per_group` (~4), `league.judge_games_per_group` (~2).
- [ ] `league.pairing` policy key (default "round_robin") `[LEAGUE]`.
- [ ] `judge.selection.*` (policy, quantile, w_len/w_amb/w_assoc/w_uniq/w_leak, length & hop bands).
- [ ] `judge.chain.len_min/len_max`, `judge.hint.max_tokens`.
- [ ] `judge.answering.undetermined = 0`.
- [ ] `judge.adjudication.*` (sentence fold, threshold, accept_synonyms, ambiguity_favors).
- [ ] `judge.anti_cheat.*` (max_hint_overlap, min_ngram, no_followup_hints, batch_only,
      deflect_verbatim_probes, commit_reveal).
- [ ] `judge.max_regens = 3`.
- [ ] `player.*` block per strategy_player §8 (n_questions, n_options, candidate_pool, question_quota,
      judge_noise, prior_floor, min_margin, min_answer_match, chain_tail_weight, use_embeddings, shot_clock).
- [ ] `corpus.source` (default "json"), `corpus.path` to bundled sample, `corpus.seed`.
- [ ] `corpus.lint.*` (min_length, max_length, require_clean_opening).
- [ ] Create `config/models.json` (judge model, player model, embed model, commentator model) — local Ollama.
- [ ] Create `config/rate_limits.json` (per-model RPM/timeout) adapted from HW6.
- [ ] Create `config/prompts.json` (judge/player/commentator prompt templates) `[RULES]`.
- [ ] Create `config/strategies.json` (aggressive/safe/adaptive question-selection profiles).
- [ ] Create `config/tuning.json` (selfplay population, bank size, objective weights, default budget tiny).
- [ ] Create `config/servers.json` (judge/player MCP url, transport, token) `[LEAGUE]`.
- [ ] Create `config/ngrok.example.yml` for the live bridge `[LEAGUE]`.
- [ ] Add `config/setup.schema.json` (JSON Schema) documenting every key.
- [ ] Write `tests/unit/test_config_files.py` asserting all shipped configs load + validate against schema.
- [ ] Assert no numeric tunable appears in `src/` (grep-based test for magic numbers in agents/game).
- [ ] Add `game.seed_default` for reproducible default runs.
- [ ] Add `logging.sink` (`stdout`|`file`) and `logging.level`.
- [ ] Add `logging.path` for the file sink.
- [ ] Add `ollama.host` and `ollama.timeout_seconds`.
- [ ] Add `embeddings.model` and `embeddings.enabled` flags.
- [ ] Add `commentary.enabled` and `commentary.model`.
- [ ] Add `analytics.elo_k` and `analytics.audit_thresholds`.
- [ ] Validate `scoring` values are numeric and non-negative in the schema.
- [ ] Validate `player.question_quota` sums to `game.n_questions`.
- [ ] Validate `judge.chain.len_min <= len_max` in the schema.
- [ ] Add a test that the quota-sum invariant is enforced (bad config → ConfigError).
- [ ] Add a test that defaults round-trip through `config.get` dotted access.
- [ ] Document each config key in `README` config section.
- [ ] Commit: "config: setup/models/rate_limits/prompts/strategies/tuning/servers + schema".

## Phase 3 — Corpus (`game/corpus.py` + linter)

- [ ] Define `Paragraph` dataclass (`id`, `text`, `opening_sentence`, `topic`, `source`).
- [ ] Define `Corpus` protocol/ABC with `sample(seed) -> Paragraph` and `all() -> list[Paragraph]`.
- [ ] Implement `JsonCorpus` reading `data/corpus.sample.json`.
- [ ] Make `JsonCorpus.sample(seed)` deterministic for a given seed.
- [ ] Implement opening-sentence extraction (split at first terminator `. ! ?`).
- [ ] Add `corpus_factory(cfg)` selecting backend by `corpus.source` (lazy heavy imports).
- [ ] Stub `WikipediaCorpus` (lazy `import`, fetch by category) `[LEAGUE]`.
- [ ] Stub `ArxivCorpus` (lazy `import`) `[LEAGUE]`.
- [ ] Implement `TextDirCorpus` (read paragraphs from a directory of `.txt`).
- [ ] Create `data/corpus.sample.json` with ≥12 diverse, game-suitable paragraphs (multi-topic).
- [ ] Ensure each sample paragraph has a clean extractable opening sentence.
- [ ] Add Hebrew + English samples to test non-ASCII handling.
- [ ] Implement `game/corpus_lint.py:check(paragraph, cfg)` returning issues list.
- [ ] Lint rule: reject too-short paragraphs (< min_length tokens).
- [ ] Lint rule: reject too-long paragraphs (> max_length tokens).
- [ ] Lint rule: reject paragraphs with no clean opening sentence.
- [ ] Lint rule: reject trivially-leaky paragraphs (opening == whole paragraph).
- [ ] Lint rule: associative-word existence heuristic (salient noun present).
- [ ] Add `lint_corpus(corpus, cfg)` running `check` over all paragraphs.
- [ ] Write `tests/unit/test_corpus.py`: `JsonCorpus.sample(seed)` reproducible.
- [ ] Test: same seed → same paragraph; different seed → (usually) different.
- [ ] Test: opening-sentence extraction on edge cases (no terminator, multiple sentences, Hebrew).
- [ ] Test linter rejects each pathological case (too short/long/no-opening/leaky).
- [ ] Test linter accepts all bundled sample paragraphs.
- [ ] Test `corpus_factory` returns `JsonCorpus` for default config.
- [ ] Verify corpus modules ≤150 lines (split backends into `corpus_backends.py` if needed).
- [ ] Commit: "engine: pluggable Corpus + corpus linter + bundled sample".

## Phase 4 — Round State & Spec (`game/round.py`)

- [ ] Define frozen `RoundSpec` dataclass: `paragraph`, `opening_sentence`, `associative_word`, `chain`,
      `hint`, `answer_key`, `salt`.
- [ ] Mark `paragraph`/`opening_sentence`/`associative_word`/`answer_key` as SECRET (docstring + naming).
- [ ] Define `PublicState` dataclass: `hint`, `chain`, `n_questions`, `n_options`, `phase`, `commit`.
- [ ] Add `RoundSpec.public()` returning only the `PublicState` (no secret fields).
- [ ] Add `RoundSpec.commit(salt)` → `sha256(salt + opening + word)` for commit–reveal.
- [ ] Define `MCQ` dataclass (`q: str`, `options: list[str]`) with a 4-option validator.
- [ ] Define `Answer` dataclass (`q: int`, `choice: int`) with a 0..3 validator.
- [ ] Define `Guess` dataclass (`opening_sentence: str`, `associative_word: str`).
- [ ] Define `RoundLog` dataclass capturing seed, config_hash, corpus_id, protocol_version, all phases.
- [ ] Add `new_round_id()` deterministic-from-seed id generator.
- [ ] Add phase-transition guard (can't answer before ask, etc.) raising `ProtocolError`.
- [ ] Write `tests/unit/test_round.py`: `public()` never exposes secret fields (introspection test).
- [ ] Test: `commit` is stable for fixed salt and changes if secret changes.
- [ ] Test: MCQ validator rejects ≠4 options; Answer validator rejects out-of-range choice.
- [ ] Test: phase guard raises on illegal transitions.
- [ ] Verify round module ≤150 lines (split dataclasses into `round_types.py` if needed).
- [ ] Commit: "engine: RoundSpec/PublicState/MCQ/Answer/Guess/RoundLog + phase guards".

## Phase 5 — Leak Guard (`game/leakguard.py`) — Tier 0.2

- [ ] Implement `normalize(text)` (lowercase, fold whitespace, strip punctuation).
- [ ] Implement `tokens(text)` and `ngrams(text, n)` helpers.
- [ ] Implement `jaccard(a, b)` token-overlap metric.
- [ ] Implement `assert_no_leak(public, spec, cfg)` raising `LeakError` on violation.
- [ ] Leak check: opening-sentence substring presence in hint/chain.
- [ ] Leak check: associative-word exact/stem/lemma match in hint/chain.
- [ ] Leak check: any ≥`min_ngram` paragraph n-gram in the public payload.
- [ ] Leak check: hint/opening Jaccard above `max_hint_overlap`.
- [ ] Implement `scan(payload, spec, cfg)` for per-answer outbound checks (default-deny field allow-list).
- [ ] Write `tests/unit/test_leakguard.py`: clean payload passes.
- [ ] Test: payload containing the opening sentence raises `LeakError`.
- [ ] Test: payload containing the associative word (exact/stem) raises `LeakError`.
- [ ] Test: payload with a long paragraph n-gram raises `LeakError`.
- [ ] Fuzz test: 200 seeded clean rounds all pass `assert_no_leak`.
- [ ] Adversarial test: a deliberately-leaky `FakeJudge` variant is caught (guard has teeth).
- [ ] Test: field allow-list rejects unexpected keys in an answer payload.
- [ ] Verify leakguard module ≤150 lines.
- [ ] Commit: "engine: leak-guard (substring/ngram/jaccard/stem) + adversarial tests".

## Phase 6 — Scoring / Referee (`game/scoring.py`) — pure, config-driven

- [ ] Define `Outcome` dataclass (`result: "win|tie|loss"`, `points: {player, judge}`, `reasons: list`).
- [ ] Implement `sentence_match(guess, opening, cfg)` (normalize + threshold similarity).
- [ ] Implement `word_match(guess, word, cfg)` (exact/stem/lemma + optional synonym set).
- [ ] Implement `determine_outcome(guess, spec, cfg)` — the single swappable referee function.
- [ ] Encode default rule: both correct → win(3); exactly one → tie(1 each); none → loss(1).
- [ ] Always award judge `scoring.judge_per_match` (+2) regardless of result.
- [ ] Branch `scoring.grade_answers`: optionally score the 20 MCQ answers vs `answer_key` `[RULES]`.
- [ ] Implement `ambiguity_favors` tie-break (default to player) in match predicates.
- [ ] Record `reasons` (which predicate passed/failed) into the outcome for transparency.
- [ ] Write `tests/unit/test_scoring.py`: WIN case (both correct) → 3/2.
- [ ] Test: TIE case (only sentence) → 1/2 player+judge.
- [ ] Test: TIE case (only word) → 1/2.
- [ ] Test: LOSS case (neither) → 1/2.
- [ ] Test: judge always +2 across all branches.
- [ ] Test: `sentence_match` tolerant of trailing period / case / whitespace.
- [ ] Test: `sentence_match` rejects a clearly-different sentence.
- [ ] Test: `word_match` accepts a configured synonym; rejects an unrelated word.
- [ ] Test: `grade_answers=true` adds MCQ-correctness points correctly `[RULES]`.
- [ ] Add a regression-test placeholder per lecturer-confirmed scoring example `[RULES]`.
- [ ] Verify scoring module ≤150 lines (split predicates into `scoring_match.py` if needed).
- [ ] Commit: "engine: pure determine_outcome referee + match predicates + full scoring tests".

## Phase 7 — Agent Protocol & Factory (`agents/`)

- [ ] Define `JudgeProtocol` (Protocol): `select_paragraph(corpus)`, `publish()`, `answer(questions)`,
      `equivalence(guess, spec)`.
- [ ] Define `PlayerProtocol` (Protocol): `seed(public, corpus)`, `ask()`, `guess(answers)`.
- [ ] Document the agent contract in `agents/__init__.py` (single source of truth).
- [ ] Implement `agents/factory.py:make_judge(kind, cfg)` (`fake` | `llm`).
- [ ] Implement `agents/factory.py:make_player(kind, cfg)` (`fake` | `llm`).
- [ ] Make factory default to `fake` when Ollama unavailable (graceful CI path).
- [ ] Write `tests/unit/test_factory.py`: factory returns objects honoring the protocols.
- [ ] Test: factory `fake` works with no network; `llm` requested without Ollama → fake fallback or clear error.
- [ ] Verify protocol/factory modules ≤150 lines.
- [ ] Commit: "agents: Judge/Player protocols + factory with fake fallback".

## Phase 8 — FakeJudge & FakePlayer (Tier 0.1, deterministic, no model/network)

- [ ] Implement `agents/fake.py:FakeJudge` honoring `JudgeProtocol`.
- [ ] FakeJudge `select_paragraph`: deterministic candidate ranking by `difficulty_score` (seeded RNG).
- [ ] FakeJudge build chain: template chain from the paragraph's salient nouns.
- [ ] FakeJudge build hint: deterministic one-liner, leak-guard-passing.
- [ ] FakeJudge `publish()`: returns `PublicState` only (no secret).
- [ ] FakeJudge `answer(questions)`: pure lookup against the cached partition `f_q` / answer_key.
- [ ] FakeJudge runs every output through the gatekeeper + leak-guard.
- [ ] Implement `FakePlayer` honoring `PlayerProtocol`.
- [ ] FakePlayer `seed`: TF-IDF/overlap prior over the corpus from hint+chain (no LLM).
- [ ] FakePlayer `ask()`: typed generators + greedy info-gain selection (deterministic).
- [ ] FakePlayer `guess(answers)`: soft Bayesian filter → argmax paragraph + chain-tail word.
- [ ] Add a `LeakyFakeJudge` test-only variant (for the leak-guard teeth test).
- [ ] Write `tests/unit/test_fake.py`: FakeJudge/FakePlayer are fully deterministic per seed.
- [ ] Test: a fixed seed yields a byte-identical `RoundLog`.
- [ ] Test: FakePlayer often wins on the bundled corpus (sanity, not flaky).
- [ ] Verify fake module ≤150 lines (split into `fake_judge.py`/`fake_player.py` if needed).
- [ ] Commit: "agents: deterministic FakeJudge/FakePlayer (no model/network)".

## Phase 9 — Player Tactics (`agents/player_tactics.py`) — strategy_player core

- [ ] Implement `CandidateSet` (paragraphs + probability distribution) with a `prior_floor`.
- [ ] Implement `tfidf_prior(hint, chain, corpus, cfg)` → seed distribution `P0`.
- [ ] Add a verbatim-chain-node bonus when a chain node appears in a paragraph.
- [ ] Implement `normalize_topk(dist, k)` keeping a tail floor.
- [ ] Implement `word_hypotheses(chain, cfg)` weighting tail nodes (`chain_tail_weight`).
- [ ] Implement question generators (pure), one per type:
- [ ] - `gen_topic(candidates)` → balanced 4-way topic split.
- [ ] - `gen_entity(candidates)` → entity-presence split.
- [ ] - `gen_lexical(candidates)` → opening-sentence surface feature split.
- [ ] - `gen_structure(candidates)` → length/shape split (data-driven quartile buckets).
- [ ] - `gen_stance(candidates)` → tone split.
- [ ] - `gen_chain(candidates, word_hyps)` → chain-anchored word-confirmation split.
- [ ] Each generator returns `(MCQ, partition f_q)` and computes the split.
- [ ] Implement `info_gain(dist, partition)` = H(before) − E[H(after)].
- [ ] Implement `select_batch(pool, dist, quota, n)` greedy submodular marginal-gain selection.
- [ ] Enforce `question_quota` per type from config.
- [ ] Reserve ≥3 chain-anchored questions.
- [ ] Implement `bayes_update(P0, questions, answers, eps)` soft Bayesian filter.
- [ ] Implement `posterior_argmax(dist)` → opening-sentence guess.
- [ ] Implement `word_from_answers(word_hyps, chain_answers)` → associative-word guess.
- [ ] Implement `confidence_report(posterior, answers, cfg)` (margin/coverage/coherence checks).
- [ ] Implement back-off to seed-prior argmax when margin < `min_margin`.
- [ ] Implement opening-sentence normalization (§4.1).
- [ ] Implement tie-aware hedging: never sacrifice a high-confidence word.
- [ ] Write `tests/unit/test_player_tactics.py`: `info_gain` = max for a perfectly-splitting question.
- [ ] Test: `info_gain` = 0 for a useless (single-bucket) question.
- [ ] Test: `select_batch` honors quotas and reserves chain questions.
- [ ] Test: `select_batch` avoids redundant near-identical questions (marginal-gain ≈ 0).
- [ ] Test: `bayes_update` recovers the true paragraph on clean answers.
- [ ] Test: `bayes_update` robust to one adversarial answer (soft `eps`).
- [ ] Test: `confidence_report` triggers back-off when margin is low.
- [ ] Test: tie-aware hedging keeps the word when sentence confidence is low.
- [ ] Test: opening-sentence normalization (trim/collapse/strip terminator).
- [ ] Implement `entropy(dist)` helper as its own pure function.
- [ ] Implement `partition_entropy(dist, partition)` helper.
- [ ] Implement `marginal_gain(dist, partition, chosen)` conditioning on already-chosen partitions.
- [ ] Implement `dedup_penalty(partition, chosen)` for redundant questions.
- [ ] Implement `quartile_buckets(values)` for data-driven structure-question edges.
- [ ] Implement `salient_entities(paragraph)` extraction for entity questions.
- [ ] Implement `topic_label(paragraph)` heuristic for topic questions.
- [ ] Implement `none_of_these_option()` always-present safe option.
- [ ] Implement `synonyms_of(word, cfg)` reading the optional synonym table.
- [ ] Implement `paraphrase_canonical(word)` deterministic canonicalization.
- [ ] Test: `entropy` of a uniform distribution equals log(n).
- [ ] Test: `entropy` of a point-mass distribution equals 0.
- [ ] Test: `quartile_buckets` produces ~balanced 4-way splits.
- [ ] Test: `none_of_these_option` is always included in every generated MCQ.
- [ ] Test: `salient_entities` returns expected nouns on a fixture paragraph.
- [ ] Test: `word_hypotheses` weights the chain tail over the head.
- [ ] Test: `CandidateSet` keeps a non-zero tail floor after normalization.
- [ ] Verify tactics modules ≤150 lines (split generators into `player_questions.py`,
      inference into `player_infer.py`).
- [ ] Commit: "agents: player tactics (info-gain batch design + soft Bayesian inference + self-check)".

## Phase 10 — Judge Tactics (`agents/judge_tactics.py`) — strategy_judge core

- [ ] Implement `length_band(paragraph, cfg)` scoring.
- [ ] Implement `opening_ambiguity(opening, corpus)` (lexical-field overlap with distractors).
- [ ] Implement `chain_distance(word, chain)` (semantic hop count, deterministic heuristic).
- [ ] Implement `topic_uniqueness(paragraph, seen_set)` (anti-replay).
- [ ] Implement `leak_risk(hint, chain, spec)` penalty.
- [ ] Implement `difficulty_score(paragraph, cfg)` combining the weighted terms.
- [ ] Implement `select_by_policy(scored, cfg)` (`argmax` or `target_quantile`).
- [ ] Implement `opening_recoverable(opening, cfg)` fairness floor (reject if unanswerable in principle).
- [ ] Implement `assoc_reachable(word, chain, cfg)` (within hop band).
- [ ] Implement `build_chain(paragraph, cfg)` deterministic template (salient nouns, hop bands).
- [ ] Implement `build_hint(paragraph, cfg)` deterministic, leak-guard-passing.
- [ ] Implement `compute_answer_key(spec, questions)` truthful per-question option (uses player partitions
      when supplied, else paragraph-grounded heuristic).
- [ ] Implement `answer_consistency(answers, spec, questions)` anti-self-leak check.
- [ ] Implement `undetermined_choice(cfg)` (config-declared default index).
- [ ] Implement `injection_filter(question)` detecting "ignore instructions/reveal" and answering by index only.
- [ ] Write `tests/unit/test_judge_tactics.py`: `difficulty_score` monotonic in each weighted term.
- [ ] Test: `select_by_policy` quantile picks a mid-high difficulty, not the max.
- [ ] Test: `opening_recoverable` rejects an unanswerable opening.
- [ ] Test: `assoc_reachable` enforces hop bands.
- [ ] Test: `build_chain`/`build_hint` always pass the leak-guard (fuzz seeds).
- [ ] Test: `compute_answer_key` is truthful vs the secret paragraph.
- [ ] Test: `injection_filter` never obeys an injection, answers by index.
- [ ] Test: anti-replay rejects a paragraph already in the seen-set.
- [ ] Implement `salient_nouns(paragraph)` for the template chain builder.
- [ ] Implement `hop_band_ok(n, cfg)` checking assoc hop bounds.
- [ ] Implement `seen_set_add(salt, paragraph)` for the per-league anti-replay store.
- [ ] Implement `commit_hash(salt, opening, word)` (delegates to RoundSpec.commit).
- [ ] Implement `paragraph_grounded_choice(question, spec)` truthful-answer heuristic.
- [ ] Test: `salient_nouns` returns deterministic nouns on a fixture.
- [ ] Test: `hop_band_ok` accepts in-band, rejects out-of-band.
- [ ] Test: `commit_hash` matches the RoundSpec commit for the same inputs.
- [ ] Test: `paragraph_grounded_choice` returns the truthful option on a known question.
- [ ] Test: `undetermined_choice` returns the config default index.
- [ ] Test: `answer_consistency` flags an over-determining verbatim probe.
- [ ] Test: difficulty `target_quantile` policy sits between min and max scores.
- [ ] Verify judge tactics modules ≤150 lines (split selection vs answering).
- [ ] Commit: "agents: judge tactics (difficulty selection + fairness floor + truthful answering + anti-cheat)".

## Phase 11 — SDK Orchestrator (`sdk/sdk.py`) — the ONLY orchestrator

- [ ] Implement `run_round(judge, player, corpus, cfg, seed)` end-to-end.
- [ ] Step: `judge.select_paragraph` → `RoundSpec` (+ commit logged before questions).
- [ ] Step: `judge.publish()` → `PublicState` (leak-guarded).
- [ ] Step: `player.seed(public, corpus)`.
- [ ] Step: `player.ask()` → 20 MCQs (validate count/options from config).
- [ ] Step: `judge.answer(questions)` → 20 answers (schema + leak-guard).
- [ ] Step: `player.guess(answers)` → `Guess`.
- [ ] Step: referee `determine_outcome(guess, spec, cfg)` → `Outcome`.
- [ ] Step: commit–reveal verification (revealed secret hashes to the logged commit).
- [ ] Implement `assemble_log(...)` → `RoundLog` with `{seed, config_hash, corpus_id, protocol_version}`.
- [ ] Add structured logging at each phase via `shared/logger`.
- [ ] Add cost/latency ledger recording per LLM edge.
- [ ] Add typed-error handling: malformed agent output → defined forfeit, never a crash.
- [ ] Implement `run_round_from_log(log)` (replay-from-seed) asserting byte-equal `Outcome` (Tier 2.4).
- [ ] Write `tests/integration/test_full_round.py`: `run_round(FakeJudge, FakePlayer)` → deterministic `Outcome`.
- [ ] Test: fixed seed → identical `RoundLog` across runs.
- [ ] Test: replay of a stored log reproduces the exact outcome.
- [ ] Test: a malformed player payload yields a forfeit outcome, not an exception.
- [ ] Test: commit–reveal mismatch is detected and flagged.
- [ ] Validate the player's question count equals `game.n_questions` before answering.
- [ ] Validate each MCQ has exactly `game.n_options` options.
- [ ] Validate the judge returns one answer per question.
- [ ] Record `started_at`/`finished_at` (via frozen clock in tests) into the log.
- [ ] Record the active player persona/strategy into the log.
- [ ] Record per-phase latency into the cost ledger.
- [ ] Surface a single `RoundResult` return type (outcome + log + ledger).
- [ ] Add a `forfeit(reason)` helper producing a defined loss outcome.
- [ ] Test: question-count mismatch → forfeit, not crash.
- [ ] Test: option-count mismatch → forfeit, not crash.
- [ ] Test: `RoundResult` contains outcome, log, and ledger.
- [ ] Verify sdk module ≤150 lines (split `assemble_log` into `sdk_log.py` if needed).
- [ ] Commit: "sdk: run_round orchestrator + assemble_log + replay-from-seed".

## Phase 12 — League (`game/league.py` + `sdk.run_league`)

- [ ] Implement `schedule(groups, cfg)` round-robin honoring ~4× player / ~2× judge per group.
- [ ] Make `schedule` a pure function returning a list of `(judge_group, player_group)` pairings.
- [ ] Implement `Standings` accumulator (points, W/T/L, as-player vs as-judge tallies).
- [ ] Implement `rank(standings)` → ordered groups (ties broken deterministically).
- [ ] Implement `grade_for_rank(rank, n_groups, cfg)` mapping (1st≈100 … last≈70).
- [ ] Implement `sdk.run_league(groups, corpus, cfg, seed)` running all scheduled rounds.
- [ ] Aggregate per-round `Outcome`s into `Standings`.
- [ ] Emit a `LeagueLog` (all rounds + final standings + grades).
- [ ] Write `tests/unit/test_league.py`: `schedule` satisfies role counts for N in {3,4,6,8}.
- [ ] Test: `schedule` is symmetric/complete (every group judges and plays the expected counts).
- [ ] Test: `Standings` accumulation across a fixed match sequence → known totals.
- [ ] Test: `rank` orders correctly with a tie-break.
- [ ] Test: `grade_for_rank` endpoints (1st→100, last→70) and monotonic in between.
- [ ] Test: `run_league` with all-Fake agents produces deterministic standings.
- [ ] Verify league modules ≤150 lines.
- [ ] Commit: "league: pure schedule + standings + rank + grade mapping + run_league".

## Phase 13 — Analytics (Tier 1.2/1.4/4.3)

- [ ] Implement `analytics/infogain.py` (pure): entropy + expected-posterior-entropy + info-gain.
- [ ] Reuse the same `info_gain` math as player tactics (single source; import, don't duplicate).
- [ ] Implement `analytics/stats.py`: win-rate, avg correct-guesses, judge-fairness, points/round.
- [ ] Add rolling-by-opponent aggregation.
- [ ] Implement `analytics/elo.py:update(rating_a, rating_b, score, k)` pure ELO.
- [ ] Track separate as-player and as-judge ratings.
- [ ] Implement `analytics/audit.py` (fairness/anti-collusion flags over match logs) `[LEAGUE]`.
- [ ] Output `ui/analytics.json` from match logs.
- [ ] Write `tests/unit/test_infogain.py`: perfectly-splitting question = max gain; useless = 0.
- [ ] Write `tests/unit/test_elo.py`: symmetry, monotonicity, fixed sequence → known ratings.
- [ ] Write `tests/unit/test_stats.py`: aggregations on hand-built logs.
- [ ] Write `tests/unit/test_audit.py`: flags an anomalous (trivially-guessable) round.
- [ ] Verify analytics modules ≤150 lines.
- [ ] Commit: "analytics: infogain + stats + ELO + fairness audit".

## Phase 14 — Strategy Profiles & Commentator (Tier 2.1/2.2)

- [ ] Implement `agents/strategy.py` registry of question-selection profiles.
- [ ] Profile `aggressive` (max info-gain), `safe` (broad category coverage), `adaptive` (re-rank after chain).
- [ ] Drive profile choice from `config/strategies.json`; player selects via config.
- [ ] Tag the active persona into the round log (UI labels it).
- [ ] Implement `agents/commentator.py` (non-scoring LLM agent narrating each phase).
- [ ] Commentator consumes round log + infogain; emits `commentary[]` into the log.
- [ ] Gate commentator behind `--commentary`; gatekept + lazy Ollama call.
- [ ] Write `tests/unit/test_strategy.py`: each profile is a pure function, deterministic.
- [ ] Write `tests/unit/test_commentator.py`: with the LLM stubbed, one line per phase, deterministic.
- [ ] Verify strategy/commentator modules ≤150 lines.
- [ ] Commit: "agents: strategy profiles + non-scoring commentator agent".

## Phase 15 — Self-Play Tuning Harness (Tier 1.3)

- [ ] Implement `tuning/selfplay.py` deterministic loop over seeds (params from `config/tuning.json`).
- [ ] Implement `tuning/optimizer.py` greedy/beam selection of a 20-question set max info-gain + no-redundancy.
- [ ] Emit `config/question_bank.tuned.json` consumed by the player (zero hardcoding).
- [ ] Keep CI budget tiny; full runs behind an opt-in flag.
- [ ] Write `tests/unit/test_optimizer.py`: deterministic per seed.
- [ ] Test: tuned set strictly beats a random set on the offline objective.
- [ ] Verify tuning modules ≤150 lines.
- [ ] Commit: "tuning: self-play harness + question-set optimizer → tuned config".

## Phase 16 — LLM Brains (`agents/judge.py`, `agents/player.py`, `agents/protocol.py`) `[RULES]`

- [ ] Implement `agents/protocol.py` prompt builders from `config/prompts.json`.
- [ ] Judge prompt: emit hint + chain (data-framed, injection-resistant).
- [ ] Judge prompt: map ambiguous question → option index only (schema-constrained).
- [ ] Player prompt: phrase the deterministic MCQs fluently (never invent options).
- [ ] Player prompt: paraphrase the opening sentence/word to canonical form.
- [ ] Define Pydantic output schemas (`extra="forbid"`) for each LLM edge.
- [ ] Implement strict decode with deterministic fallback (degrade to Fake path, never crash).
- [ ] Implement `JudgeAgent` (LLM) wrapping judge tactics + gatekeeper + leak-guard.
- [ ] Implement `PlayerAgent` (LLM) wrapping player tactics + gatekeeper.
- [ ] Wire `max_regens` retry with a tighter prompt on leak-guard rejection.
- [ ] Add `BEFORE editing prompts, consult claude-api skill if Claude/Anthropic is ever used` note (we use Ollama).
- [ ] Write `tests/unit/test_protocol.py`: prompt builders interpolate config without leaking secrets.
- [ ] Test: malformed LLM JSON → deterministic fallback equals Fake output.
- [ ] Test: JudgeAgent output always passes leak-guard (LLM stubbed with a leaky reply → caught + regen).
- [ ] Test: PlayerAgent never emits non-config option counts.
- [ ] Verify brain modules ≤150 lines (split prompt templates loading into `protocol_prompts.py`).
- [ ] Commit: "agents: LLM Judge/Player brains + strict-decode protocol with fallback".

## Phase 17 — MCP Servers & Client (`mcp/`) — adapt HW6, lazy fastmcp

- [ ] Implement `mcp/contract.py`: dataclasses for `publish`/`ask`/`answer`/`guess` + `validate(payload, kind)`.
- [ ] Echo `PROTOCOL = "q20/1"` in every envelope; reject mismatched majors with `ProtocolError`.
- [ ] Implement `mcp/judge_server.py` (FastMCP, lazy import) exposing publish/answer tools.
- [ ] Implement `mcp/player_server.py` (FastMCP, lazy import) exposing ask/guess tools.
- [ ] Implement `mcp/client.py` (lazy) calling the remote tools + validating responses.
- [ ] Implement `mcp/bridge.py` adapting HW6 `cross.py` (ngrok/login) for inter-group play `[LEAGUE]`.
- [ ] Implement a `--local` mode running both servers in one process (CI/dev).
- [ ] Put connection params (`url`, `transport`, `token`) in `config/servers.json` (zero hardcoding).
- [ ] Ensure the judge server only ever serializes `PublicState` (no secret) — leak-guard at the boundary.
- [ ] Write `tests/integration/test_mcp_wire.py`: in-process local bridge plays a full round.
- [ ] Write `tests/unit/test_contract.py`: `validate` accepts good payloads, rejects bad shapes.
- [ ] Test: protocol-major mismatch raises `ProtocolError`.
- [ ] Test: judge-server payload never contains a secret field (introspection).
- [ ] Omit server entry-point modules from coverage (mirror HW6 `omit`).
- [ ] Verify MCP modules ≤150 lines.
- [ ] Commit: "mcp: versioned contract + judge/player servers + client + local bridge".

## Phase 18 — CLI (`cli/main.py`) — thin, SDK-only

- [ ] Implement `cli/main.py` argparse with subcommands.
- [ ] `q20 play-round --fake` → run a deterministic round, print + write a scored log.
- [ ] `q20 play-round --replay <log>` → replay-from-seed, assert byte-equal outcome.
- [ ] `q20 play-round --commentary` → include commentator narration.
- [ ] `q20 run-league [--email]` → schedule + run + standings (+ optional digest).
- [ ] `q20 serve` → static-serve `ui/` + emit `ui/league.json` and `ui/round/<id>.json`.
- [ ] `q20 report [--analytics]` → write analytics/stats output.
- [ ] `q20 tune [--full]` → run the self-play tuning harness.
- [ ] `--seed`, `--config-dir`, `--corpus` global flags (zero hardcoding).
- [ ] Ensure CLI imports only the SDK (no direct agent/game wiring).
- [ ] Make CLI exit codes meaningful (0 success, non-zero on forfeit/error).
- [ ] Write `tests/integration/test_cli.py`: `play-round --fake` exits 0 with a scored log.
- [ ] Test: `--replay` reproduces the outcome.
- [ ] Test: unknown subcommand → clear error + non-zero exit.
- [ ] Omit CLI from coverage (mirror HW6).
- [ ] Verify CLI module ≤150 lines (split subcommands into `cli_commands.py` if needed).
- [ ] Commit: "cli: thin SDK-only entrypoint (play-round/run-league/serve/report/tune)".

## Phase 19 — Web UI (Tier 1.1) — adapt HW6 `ui/`

- [ ] Copy HW6 `ui/{app.js,theme.css}` as a starting point.
- [ ] Create `ui/standings.html` (sortable table: rank, pts, W/T/L, as-player vs as-judge, ELO).
- [ ] Create `ui/replay.html` (step-through: hint → 20 Q/A → guesses → score).
- [ ] Replace the Monopoly board renderer with a "transcript" renderer in `app.js`.
- [ ] Keep the HW6 timeline scrubber + theming + live-poll loop.
- [ ] Highlight the chosen MCQ option per question; reveal the secret only at the end.
- [ ] Add an analytics side panel (info-gain per question) reading `ui/analytics.json`.
- [ ] Add a cost/latency panel proving local cost = $0.
- [ ] Add a commentary side panel reading `commentary[]` from the round log.
- [ ] Create `ui/sample_round_log.json` (deterministic Fake round) for offline UI dev.
- [ ] Create `ui/GEMINI_ASSET_PROMPTS.md` (hero/trophy prompts in house style).
- [ ] Wire `q20 serve` to regenerate `ui/league.json` + per-round logs.
- [ ] Add a "next/prev question" stepper control to the replay.
- [ ] Add an autoplay toggle that advances the round on a timer.
- [ ] Render the hint + chain header at the top of the replay.
- [ ] Render the player's belief distribution as a bar per candidate paragraph.
- [ ] Animate the belief update as each answer is revealed.
- [ ] Render the final guess vs the revealed secret side-by-side.
- [ ] Color-code win/tie/loss in the outcome banner.
- [ ] Make the standings table column-sortable (click a header).
- [ ] Add a per-group filter to the standings view.
- [ ] Add a dark/light theme toggle (reuse HW6 theme.css).
- [ ] Ensure the UI degrades gracefully when `analytics.json` is absent.
- [ ] Add a favicon + page title for the league.
- [ ] Manually verify the UI renders the sample round + standings in a browser.
- [ ] Commit: "ui: standings + round-replay web UI (adapted from HW6) + asset prompts".

## Phase 20 — Email Digest (Tier 4.2) — adapt HW6 report/mailer `[LEAGUE]`

- [ ] Adapt `report/reporter.py` to build a league standings digest (text + HTML).
- [ ] Adapt `report/mailer.py` (lazy `google` import) to send via Gmail.
- [ ] Adapt `tools/google_auth.py` OAuth flow; store creds under gitignored `secrets/`.
- [ ] Wire `q20 run-league --email` to send the digest after the league completes.
- [ ] Write `tests/unit/test_reporter.py`: digest builder produces expected text from a fixed standings.
- [ ] Write `tests/unit/test_mailer.py`: with Gmail stubbed, message is assembled correctly (no network).
- [ ] Omit `tools/`/mailer from coverage (mirror HW6).
- [ ] Document the OAuth setup in README.
- [ ] Commit: "report: league standings digest + Gmail mailer (lazy, opt-in)".

## Phase 21 — Robustness / Adversarial Test Pack (Tier 2.3)

- [ ] Parametrized test: malformed opponent payloads → typed exception or forfeit, never crash.
- [ ] Test: fewer/more than `n_options` options rejected by contract/MCQ validator.
- [ ] Test: duplicate questions handled (deduped or penalized, never crash).
- [ ] Test: empty chain handled gracefully.
- [ ] Test: judge that always answers "A" → player still degrades to seed argmax.
- [ ] Test: non-UTF8 / Hebrew text round-trips through the whole pipeline.
- [ ] Test: prompt-injection question (LLM judge stubbed) is answered by index, never obeyed.
- [ ] Test: oversized payloads rejected by the contract.
- [ ] Test: a judge that tries to leak via the answer channel is blocked by the leak-guard.
- [ ] Test: replay determinism under a config change is detected (config_hash mismatch flagged).
- [ ] Commit: "tests: adversarial/robustness pack (malformed inputs, injection, leaks)".

## Phase 22 — Coverage, Lint & 150-Line Hardening

- [ ] Run `uv run ruff check src tests`; fix all findings.
- [ ] Run ruff with `--fix` for safe autofixes; review the diff.
- [ ] Run `uv run pytest`; confirm ≥85% coverage.
- [ ] Identify uncovered lines; add targeted tests (not coverage-padding).
- [ ] Run `scripts/check_line_limit.py`; split any `src/` file >150 lines.
- [ ] Verify every module's public functions have docstrings.
- [ ] Verify no `print` in library code (use the logger).
- [ ] Verify no hardcoded numeric tunables in `src/` (grep test green).
- [ ] Verify all heavy imports (`fastmcp`, `google`, embeddings) are lazy.
- [ ] Verify `FakeJudge`/`FakePlayer` path needs no network in CI.
- [ ] Run the full test suite offline (disable network) to prove CI-safety.
- [ ] Confirm CI is green on a pushed branch.
- [ ] Commit: "harden: ruff clean, ≥85% coverage, ≤150-line files verified".

## Phase 22b — Cross-Cutting Test & Quality Details

- [ ] Add `tests/conftest.py` with shared fixtures (sample corpus, default config, fixed seed).
- [ ] Add a `frozen_clock` fixture so timestamps are deterministic in logs.
- [ ] Add a `stub_ollama` fixture injecting canned LLM replies (no network).
- [ ] Add a `network_blocked` fixture that fails any socket call (prove CI offline-safety).
- [ ] Add a `tmp_config_dir` fixture writing test configs.
- [ ] Add a parametrized "all configs load" smoke test.
- [ ] Add a test asserting `PROTOCOL` major matches the contract envelope.
- [ ] Add a test that `assemble_log` round-trips to/from JSON.
- [ ] Add a test that every dataclass is JSON-serializable.
- [ ] Add a test that the `Q20_CONFIG_DIR` override is honored.
- [ ] Add a test that `clear_cache` actually re-reads config from disk.
- [ ] Add a property test: `normalize(normalize(x)) == normalize(x)` (idempotent).
- [ ] Add a property test: leak-guard is symmetric to whitespace/case changes.
- [ ] Add a test that the FakePlayer never emits more than `n_questions`.
- [ ] Add a test that the FakeJudge always returns exactly `n_questions` answers.
- [ ] Add a coverage check that `determine_outcome` branches are all exercised.
- [ ] Add a mutation-style sanity test (flip an answer → outcome changes).
- [ ] Add a `pytest.mark.slow` marker for the self-play full run (excluded in CI).
- [ ] Verify all test modules import without side effects.
- [ ] Commit: "tests: shared fixtures + cross-cutting invariants + offline-safety guards".

## Phase 23 — Documentation

- [ ] Write README: project pitch + the 20-Questions game rules.
- [ ] README: architecture diagram (layers from plan.md).
- [ ] README: how-to-run (`uv sync`, `q20 play-round --fake`, `serve`, `run-league`).
- [ ] README: how-to-join-the-league (MCP handshake, config/servers.json) `[LEAGUE]`.
- [ ] README: config reference table (every key in `config/*.json`).
- [ ] README: the deterministic-engine / LLM-at-edges design rationale.
- [ ] README: anti-cheat / leak-guard / commit–reveal fairness section.
- [ ] README: declare the public `undetermined` default index (no side-channel).
- [ ] README: scoring rules + the swappable `determine_outcome` seam `[RULES]`.
- [ ] README: creativity/extension list (analytics, ELO, tuning, commentator, UI).
- [ ] Add `docs/architecture_review.md` (mirror HW6) — self-review vs the rubric.
- [ ] Add screenshots/GIF of the UI to README.
- [ ] Write per-member Moodle submission PDF checklist.
- [ ] Add CHANGELOG.md tracking the granular commits.
- [ ] README: badges (CI status, coverage, ruff).
- [ ] README: the league grade-mapping (1st≈100 … last≈70) explanation.
- [ ] README: a worked example round (hint→chain→Q/A→guess→score).
- [ ] README: troubleshooting (Ollama down, model missing, Hebrew path).
- [ ] README: contribution/handshake guide for another group to join.
- [ ] docs: add a sequence diagram of `run_round` phases.
- [ ] docs: add a data-flow diagram (secret vs public surface).
- [ ] docs: document the leak-guard threat model.
- [ ] docs: document the commit–reveal audit protocol.
- [ ] docs: list every CLI command with examples.
- [ ] Commit: "docs: README + architecture review + config reference".

## Phase 24 — Final Verification & Submission

- [ ] End-to-end: `q20 play-round --fake` exits 0 with a scored, leak-clean log.
- [ ] End-to-end: `q20 run-league` (all Fake) produces standings + grades deterministically.
- [ ] End-to-end: `q20 serve` shows standings + a replay in the browser.
- [ ] End-to-end: a real Ollama round (judge=qwen2.5, player=aya) plays locally `[RULES]`.
- [ ] Confirm $0 cost ledger on a full league run (no API key used).
- [ ] Re-run ruff + pytest + line-limit gate; all green.
- [ ] Tag a release `v1.0.0`.
- [ ] Create the private GitHub repo `q20` (or per course naming).
- [ ] Invite the graders (rmisegal + ShalDag1) per course convention.
- [ ] Push all granular commits + the tag.
- [ ] Each member exports the Moodle PDF.
- [ ] Update memory (MEMORY.md) with final-project status.
- [ ] Commit: "release: v1.0.0 — q20 league ready".

## Phase 25 — Stretch / Rank-Mover Extensions (creativity axis)

- [ ] Embedding re-rank for the player prior (graceful off without an embed model).
- [ ] Glicko ratings alongside ELO (separate as-player/as-judge).
- [ ] Live league dashboard auto-refresh (reuse HW6 live-poll).
- [ ] Per-question expected-score heatmap in the replay UI.
- [ ] Judge "difficulty dial" demo (quantile slider regenerating rounds offline).
- [ ] Multi-language corpus showcase (English + Hebrew round in the same league).
- [ ] Tournament bracket mode (knockout) on top of round-robin `[LEAGUE]`.
- [ ] Anti-collusion audit surfaced in the standings UI `[LEAGUE]`.
- [ ] Match reproducibility badge (seed + config_hash) shown in the replay.
- [ ] A `q20 doctor` command checking Ollama/config/corpus health before a league.
- [ ] Caching of paragraph partitions across a league (perf) — keep determinism.
- [ ] Export a per-match audit bundle (log + commit + reasons) for appeals `[LEAGUE]`.
- [ ] Commit: "stretch: ratings/dashboard/heatmap/doctor/audit extensions".

---

### PRD requirement → phase coverage map (traceability)

- Two agents Judge + Player → Phases 7-10, 16.
- Judge picks paragraph + hint + associative chain → Phases 4, 10, 16.
- Player 20 MCQ (4 options) in one batch → Phases 4, 9, 16.
- Judge answers; Player guesses opening sentence + associative word → Phases 9-11, 16.
- Deterministic referee scoring (win3/tie1/loss1/judge+2) → Phase 6.
- Provisional `determine_outcome` swappable + config scoring → Phases 2, 6 `[RULES]`.
- League round-robin (~4× player / ~2× judge), standings → grade → Phase 12.
- Pluggable corpus + bundled sample → Phase 3.
- MCP transport / inter-group bridge → Phase 17 `[LEAGUE]`.
- Injected FakeJudge/FakePlayer, no model/network in CI → Phases 8, 11.
- Leak-guard / answer isolation → Phase 5.
- Zero hardcoded params (all config) → Phase 2 + grep test in 22.
- ≤150-line files, ruff, pytest ≥85%, CI → Phases 0, 22, 24.
- Lazy heavy imports (fastmcp, google) → Phases 1, 17, 20.
- Local Ollama / no API key → Phases 1, 16, 24.
- Web replay/standings UI (stretch) → Phase 19.
- Email digest (stretch) → Phase 20 `[LEAGUE]`.
- Creativity/out-of-the-box extensions → Phases 13-15, 25.
- Vibe-Coding lifecycle (prd/plan/todo) → this file + docs.
