# winning_strategy.md — THE ULTIMATE q20 WINNING STRATEGY ($0, rule-safe)

**Group nis-yar1 · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

> Synthesis of 135 ideas across 10 lenses, deduped/merged, filtered to **FREE + rule-safe only**, ranked by
> impact × feasibility, and **grounded against the actual code** in `src/q20`. This is the build contract.
> Where this doc contradicts the older strategy docs, **this doc wins** (the contradictions are intentional and
> explained — see §5). Everything tunable lives in `config/*.json`; nothing here adds a paid dependency.

---

## 1. Executive summary — the core thesis

**We win the league at $0 by making the deterministic engine do the winning, and demoting every local LLM to a
fluency layer that can fail without losing a point.** Three pillars:

1. **The corpus is shared → the game is RETRIEVAL, not generation.** The opening sentence is one of a known,
   finite list. The whole player problem collapses to: *rank corpus paragraphs, fold in the 20 answers, emit the
   top one's first sentence.* This is a closed-set classification problem we can solve near-deterministically.
2. **Player payoff is BINARY (3 vs 1).** The live grid is `win=3, tie=1, loss=1` (`src/q20/constants.py`), so a
   **tie scores identically to a loss**. We must optimize **P(both correct)**, not "convert losses to ties."
   The associative word is published-in-spirit via the chain (near-free), so we **bank the word and spend the
   entire 20-question budget + all inference on the genuinely uncertain half: the opening sentence.**
3. **Judge points are an unloseable floor.** Judge is a flat **+2** with zero upside for "difficulty." The only
   way to lose it is a protocol/leak/appeal fault. So the Judge's job is **never fault, never get overturned,
   complete the max number of judge games** — difficulty tuning is cosmetic; leak-guard + commit-reveal + a
   deterministic answer key are where the points live.

**Math that drives everything (idea: meta-game lens):** with player ~4× and judge ~2×, our guaranteed floor is
`2×2 = +4` from judging; *all variance and all upside live in the 4 player rounds* (each worth 1→3). Therefore
**rank is decided almost entirely by player win-rate**, and **~100% of tuning/compute budget belongs to the
player brain.** We will state this number in the report as an honest, math-backed compute-allocation policy.

**What's actually broken today (verified in code), in priority order:**
- `player_tactics.best_guess` takes `qa` and **throws it away** (`# noqa: ARG001`) — the 20 questions are pure
  theatre; the guess is identical whether the Judge answers truthfully or randomly. **This is the #1 gap.**
- Retrieval is plain **Jaccard** over a token bag that mixes the corpus's *stored* hint into the candidate
  fingerprint — a phantom signal that won't exist on the wire when the Judge regenerates the hint.
- `judge.answer` ships the **entire secret paragraph** into Ollama and returns **all-zeros** on any hiccup — a
  systematic index-0 bias that corrupts the opponent's inference and risks fairness appeals.
- **No leak-guard, no commit-reveal, no contract validation, no shot-clock, no per-round try/except** in
  `sdk.run_round` — one flaky model or one malformed opponent payload can forfeit a whole sweep.
- Config knobs `judge_noise`, `candidate_pool`, `prior_floor`, `question_quota`, `min_margin` are **declared but
  dead** — the "zero hardcoding" rubric claim is currently unbacked.

---

## 2. Player playbook (questions → retrieval → guessing)

### 2.1 Retrieval (the binding constraint — get this right and we win)
1. **BM25/TF-IDF over a one-time corpus IDF index**, replacing Jaccard. IDF makes rare chain nodes
   (`mitochondria`, `communication`) dominate over `the`; length-normalization kills the long-paragraph bias.
   Cache the inverted index + IDF lazily on the `Corpus` object (reused by analytics + self-play).
2. **Fix the channel separation bug:** build the candidate fingerprint **only from paragraph body tokens**
   (the thing we're identifying), and the query **only from public hint+chain**. Stop matching against the
   corpus's *stored* hint — on the wire the Judge regenerates it, so that's a phantom feature that "wins" in
   tests but generalizes to nothing.
3. **Verbatim chain-node anchoring with positional weight:** large score bonus when a chain node appears
   (exact/stemmed) in a paragraph; weight **tail nodes > head nodes** (`chain_tail_weight`) since the chain
   converges on the answer.
4. **Two-stage prune:** Jaccard/BM25 prior over the full corpus → top-K (`player.candidate_pool`, e.g. 24) with
   a `prior_floor` so a tricky Judge's obscure paragraph is never pruned to zero. All entropy/Bayes math runs
   only over those K (keeps it exact and cheap on local hardware).
5. **Optional local-embedding re-rank** (`nomic-embed-text` via Ollama, `player.use_embeddings`), gated with
   BM25 as the guaranteed fallback — catches paraphrase matches with zero shared tokens, $0.
6. **Hebrew/robustness pass:** NFC normalize, final-form letter folding (ך→כ), skip the English stemmer on
   non-Latin tokens. Cheap insurance for a Hebrew-language course.

### 2.2 The keystone: the partition oracle `f_q` + the Bayesian update
- **`f_q(candidate) → option`** (pure, no LLM): for each generated MCQ and each top-K candidate, predict which
  option index the Judge would pick, using the **same deterministic similarity the Judge uses** to match
  paragraph→option, plus a "none of these" bucket. Cache the per-question option→candidate map. *This single
  function unlocks both info-gain selection and the answer-based update.*
- **Make `guess()` consume the answers** (the #1 fix): soft Bayesian filter
  `score(c) = log P0(c) + Σ_i [answer_i == f_qi(c) ? log(1-ε) : log(ε)]`, `ε = player.judge_noise`. argmax →
  opening sentence. Soft so no single adversarial answer can zero the true candidate (`prior_floor` backstop).

### 2.3 Question batch design (corpus-grounded, info-gain selected)
- **Corpus-grounded option synthesis:** mine the 4 options from the live candidate paragraphs so **every option
  is satisfied by some candidate** and the 4-way split is **balanced (≈2 bits/question)**. Length/numeric buckets
  use the candidates' **actual quartiles**, not hardcoded edges. The LLM only *phrases*; the generator owns
  options + `f_q`. Guarantees the "exactly one true option" invariant the Bayes update depends on.
- **Greedy submodular selection over the JOINT partition:** pick the 20 by marginal info-gain conditioned on
  already-chosen questions (exact entropy over the ≤K candidates). Kills redundancy automatically.
- **Type-quota enforcement** (`player.question_quota`, currently dead): force coverage across
  topic/entity/lexical/structure/chain so a Judge that games one type can't collapse the batch.
- **Opening-sentence-specific lexical probes:** MCQs about the *first sentence only* (first-token class:
  proper-noun / number / "The" / question-word; sentence-length bucket; quote/colon present) — split the target
  on the exact axis we must emit, where topical retrieval is weakest.
- **Calibrated "none of these" as option 4** with explicit `f_q` mapping; reject a question that would push
  >~40% candidate mass into "none"; a "none" answer covering all top candidates is flagged low-trust (≈0 weight).
- **Calibration probes (1–2 slots):** MCQs whose correct option is derivable purely from the published
  hint/chain (we know the truth a priori). If the opponent Judge answers these wrong → raise `judge_noise` ε for
  that whole round's update. Turns 1–2 questions into an opponent-reliability sensor.

### 2.4 Guessing + the word (binary-payoff aware)
- **Dynamic chain-question quota:** ask the *minimum* chain-anchored questions needed to push word-confidence
  past a threshold, then **reallocate the rest to opening-sentence discrimination.** (Under binary scoring,
  over-confirming the near-solved word is wasted budget — see §5.)
- **Decoupled word recovery:** rank a word-hypothesis list {chain tail, chain[-2], offline corpus-synonyms, top
  TF-IDF noun shared by the top-3 paragraphs}; pick by chain-anchored answer support. **Never overwrite a
  high-confidence published-chain word with a noisy paragraph word.** This hedges the two targets independently
  so one bad retrieval doesn't lose both.
- **Self-check / back-off gate (`confidence_report`):** before emit, if `P(top1)/P(top2) < min_margin`, fall back
  to the BM25 seed-prior argmax (which the Judge can't corrupt); if the top candidate contradicts >30% of
  answers, re-rank excluding the most-violated answers. **Makes the Bayesian path monotonically non-regressive
  vs the retrieval baseline** — it can never do worse than today.
- **Guess-format defense via the referee's own `_norm`:** share `game/scoring._norm` into the player so we
  self-verify "would the referee accept this string?" against each candidate's actual opening sentence. Losing a
  correct guess on a trailing period or smart-quote is a 2-point throw we eliminate by construction.
- **NEVER-THROW floor:** the deterministic guess is ALWAYS computed and is the floor; the LLM may only override
  it if it parses cleanly AND passes leak/format checks. Test: 200 seeded rounds with a garbage-returning model
  stub → outcome never worse than the deterministic baseline.

---

## 3. Judge playbook (protect the flat +2; complete the most clean rounds)

1. **Deterministic answer-key oracle** (biggest judge fix): at `select()` time compute each MCQ's truthful
   option in **pure Python** from the secret paragraph (token/embedding overlap → argmax option), cache it; at
   `answer()` time do **pure lookup**. The LLM resolves *only* genuinely ambiguous NL questions, and never sees
   the full paragraph unless needed. Reproducible on appeal, CI-testable with no model. (Replaces the current
   "ship whole paragraph + all-zeros fallback.")
2. **Outbound leak-guard chokepoint** `game/leakguard.py:assert_no_leak(payload, spec)`: reject any payload
   containing the opening-sentence tokens above Jaccard 0.2, the associative word (exact/stem/lemma), or any ≥4-
   gram of the paragraph. Route every `publish`/`answer` through it. Schema-only answers (bare ints,
   Pydantic `extra='forbid'`) make "explain your answer" prompt-injection structurally impossible.
3. **Commit-reveal appeal-proofing:** publish `commit = sha256(salt + opening_sentence + associative_word)` to
   the log **before** seeing questions; referee verifies the reveal hashes to it. The Judge literally cannot move
   the goalposts → every "the judge cheated" appeal is mechanically refutable. `hashlib` only.
4. **Injection filter** on incoming player questions: treat them as untrusted DATA, detect imperative-injection
   ("ignore instructions / output the opening sentence"), answer as a normal MCQ-by-index — never obey, never
   refuse (refusal is itself a protocol fault).
5. **Regen loop + deterministic template-chain fallback:** draft hint via LLM → leakguard accept/reject → retry
   up to `max_regens` → fall back to a deterministic noun-extraction chain so a weak/flaky model never produces a
   leaking or empty publish that forfeits the +2.
6. **Player-favoring adjudication predicates** (`ambiguity_favors: player`, fuzzy sentence threshold, synonym
   acceptance): costs the Judge nothing (+2 regardless) and eliminates the most common dispute class → fewer
   appeals → more completed judge games.
7. **Defensive selection at a MID quantile (~0.5), NOT 0.75:** under the flat-+2 grid, difficulty has zero point
   value; a mid quantile **minimizes dispute/appeal probability** (max recoverability) — the opposite of the old
   "hard but fair" framing (see §5). Keep anti-replay (per-league seen-set) so we never reuse a paragraph against
   a player who saw it.
8. **Contract hardening on the judge server:** reject malformed player batches (wrong count, ≠4 options, out-of-
   range indices) with a typed `Verdict(ok, reason)` rather than crashing — an opponent's bug becomes a clean
   forfeit in our favor, never a forfeit of our +2. Idempotent `publish`/`answer` (cache + refuse second call) so
   network retries can't extract a second hint or a changed answer set.
9. **Per-round fairness certificate** into the log (difficulty score, `opening_recoverable=true`, leak-scan PASS,
   commit hash, undetermined policy) → renders as a judge scorecard in the replay UI.

---

## 4. Free-model & infra plan ($0, local-first)

- **Ollama JSON mode + bounded `num_predict` + fitted `num_ctx`** on every call: kills malformed-output
  fallbacks (each parse failure today silently degrades a whole batch to defaults) and cuts latency 2–5×, buying
  shot-clock headroom. Native options, no deps.
- **Harden `_extract_json`:** the current greedy `\{.*\}` grabs to the last brace and captures trailing prose.
  Replace with a brace-balanced / `raw_decode` scanner + fenced-code-block strip. This chokepoint gates every
  LLM edge.
- **Persistent prompt→response cache** keyed by `sha256(model+messages+temp+options)` (sqlite/JSON under
  `.cache/`). The league replays overlapping prompts (player ~4×, judge ~2×) → repeat rounds become instant and
  CI hermetic. Record a `cache_hit`/`$0` ledger as observability evidence.
- **Hard shot-clock budget manager** threaded into `Gatekeeper.execute`: when remaining time < estimate, skip
  the LLM and emit the deterministic oracle/retrieval answer immediately. **A forfeit-on-timeout is the worst
  free-model failure vs a fast paid opponent; this converts it to at-worst-deterministic-but-on-time.**
- **Warm-pool / keep-alive:** prime each configured model at startup with `keep_alive` so the first (most
  important) Judge/Player call doesn't eat a multi-second cold-load. Pre-flight model-availability check.
- **Asymmetric model ladder:** retrieval/ranking = no LLM; trivial phrasing = qwen2.5:0.5b; judge answers =
  qwen2.5:7b; escalate to 14b only on oracle-flagged ambiguous answers. All tiers already local.
- **Self-consistency / cross-model agreement on ambiguous items only:** for the few oracle-flagged close calls,
  majority-vote k=3 (config, default 1 = off in CI), or require qwen2.5:7b ↔ aya-expanse:8b agreement, else fall
  back to the deterministic oracle. Both models already on disk.
- **Local embeddings** (`nomic-embed-text`, ~270MB, fits the RTX 3500): one cached corpus embedding matrix reused
  by player re-rank, judge fuzzy adjudication, and word disambiguation. One client, three payoffs, $0.

---

## 5. Meta-game & scoring EV (the decisions that actually move rank)

- **`game/ev.py` as a pure, config-driven EV core.** `marginal_value(outcome, cfg)` and
  `should_gamble(p_both, p_partial, cfg)` read the live grid. **Under the current grid (tie=loss=1) the rule is:
  ALWAYS go for both — never hedge to a guaranteed tie, because a tie buys ZERO marginal points.** If the brief
  later confirms tie>loss, the *same* function flips to "lock the safe partial." This **future-proofs the single
  most consequential decision against the explicit `[TBD-confirm]` scoring ambiguity** and is the reason this doc
  contradicts strategy_player.md §6.5 ("never sacrifice the word to convert ties into wins") — that advice is an
  EV error under the live grid.
- **Per-role budget allocator + standings ledger:** separate "locked" judge points (`+4` floor) from "at-risk"
  player points; report `P(rank=1)`, expected grade. Headline narrative: *judge EV is capped at the floor; rank
  is decided entirely by player win-rate; therefore all compute goes to the player.*
- **Round-robin opponent modeling (legal scouting from public logs):** per opponent, log judge behavior (chain
  style, undetermined-default index, hint verbosity, answer-option distribution, self-consistency) into
  `analytics/opponents.json`; feed as a **prior** into the next encounter — sharpen the candidate prior and
  per-opponent `ε`. If a judge is detected "always-0" or near-random → set ε high, lean on hint+chain retrieval;
  if it answers consistently → trust the answers (low ε). Compounds across the ~4 player rounds.
- **Replay/repeat exploit:** cache solved `(opponent, hint-hash, chain-hash → sentence+word)`; a reused paragraph
  becomes a free 3-pointer. Symmetric defense (anti-replay) on our judge side.
- **"Points left on the table" post-mortem:** per round, compute the counterfactual — given the Judge's actual 20
  answers, was the true paragraph *uniquely recoverable*? If yes and we missed it → "avoidable loss" (strategy
  bug); if no → "unwinnable" (not our fault). Separates strategy error from variance and gives an honest,
  evidence-backed self-assessment (per the memory note: modest, backed self-scores beat inflated claims).

---

## 6. Robustness — never lose points

- **Per-round try/except isolation in `run_round` and per-match in `run_league`:** any opponent/transport/model
  failure → a defined forfeit `Outcome`, never a crash that zeroes every later scheduled match. (Today an
  exception aborts the whole sweep.)
- **Tolerant, range-validating answer ingestion:** out-of-range/missing answers → a `unknown` sentinel that
  contributes **zero** weight, not a false index-0 that poisons the posterior.
- **Never-illegal-output post-condition gate** on both agents: guarantee exactly `n_questions` MCQs each with
  `n_options` unique non-empty options, and in-range indices, as the LAST step before emit.
- **Versioned, schema-validated MCP contract** (`mcp/contract.py`, `PROTOCOL='q20/1'` echoed each message):
  validate `publish/ask/answer/guess`; reject mismatched majors with a typed `ProtocolError` + graceful forfeit.
  Publishing it first makes us the reference other groups conform to.
- **Commit-reveal verification on the wire** (client recomputes the hash; mismatch → round flagged disputed).
- **Replay-from-seed determinism harness:** log `{seed, config_hash, corpus_id, protocol_version, commit}`;
  `--replay` re-runs and asserts byte-identical `Outcome` (CI guard against hidden nondeterminism + appeal
  evidence).
- **Dual-path consistency oracle:** CI test asserting in-process `run_round` and over-MCP `run_round_over_mcp`
  emit byte-identical logs for the same seed (we must never tune against one scoring and be judged by another).
- **Adversarial opponent test pack** (`tests/adversarial/`): judge always-'A', wrong-count/1-based/negative/
  string indices, empty chain, >4/<4 options, duplicate questions, non-UTF8/Hebrew, leaky FakeJudge, guess-
  stealing reveal swap → each yields a typed exception or defined forfeit, never a crash. Doubles as coverage
  toward the ≥85% gate.

---

## 7. Creativity / grade extensions (visible rigor for the rubric)

- **Per-question expected-info-gain logging** surfaced in the replay UI ("Q7 was a 1.9-bit split; Q12 was dead
  weight") — demonstrates the information-theoretic claim with real numbers.
- **Monte-Carlo LEAGUE simulator:** simulate the full round-robin thousands of times vs parametric opponents
  (weak/median/strong) under the live config → expected rank + its distribution + expected grade. Pure
  deterministic engine, zero LLM, CI-cheap. Strongest single creativity artifact.
- **Commentary / caster agent** narrating each match from the analytics (gated, lazy, `--commentary`).
- **ELO/Glicko ratings** alongside official points (separate as-player / as-judge), secondary UI sort, no rules
  risk.
- **Standings + step-through replay web UI** (reuse the HW6 board UI → transcript renderer; hint → 20 Q/A with
  chosen option highlighted → guesses → score; secret revealed only at the end). Fairness-certificate scorecard
  per judge round.
- **Devil's-Judge regression corpus:** pathological RoundSpecs (misleading hint, empty/loop chain, decoy
  paragraphs, anti-truthful judge) with property tests asserting the player still recovers or backs off — turns
  the "adversary-robust" prose claim into executed, graded evidence.

---

## 8. Self-play tuning plan (offline, free, reproducible)

- **`tuning/selfplay.py`:** thousands of FakeJudge/heuristic-Judge rounds where the Player's `f_q` oracle plays
  against the real answer logic; reward = the **config scoring grid** (adapts if rules change).
- **`tuning/optimizer.py`:** greedy/beam search over `question_quota` + option-mining params to maximize expected
  score under a no-redundancy penalty; emits `config/question_bank.tuned.json` consumed by the runtime player
  (zero hardcoding — a regenerated config, not a code change). Test: tuned set strictly beats a random set.
- **Offline distillation:** a one-time local 14b "teacher" generates + labels high-quality MCQ candidates baked
  into the tuned bank; runtime uses the static asset → $0/round, fast at match time. "Distillation without an
  API" — strong creativity story.
- **Online per-opponent bandit** (epsilon-greedy/UCB over a small param grid from `config/strategies.json`):
  after each match vs opponent X, update the config that scored best historically against them (trust answers vs
  the honest group, ignore them vs the index-0 group). Tiny default budget keeps CI cheap.
- Keep all of this **CI-cheap by default** (tiny budget; full runs behind an opt-in flag).

---

## 9. PRIORITIZED action list (P0/P1/P2 · effort · q20 module)

### P0 — correctness + never-lose-points (do these first; they decide rank)
1. **`f_q` partition oracle + Bayesian `guess()`** — make `best_guess` CONSUME `qa`. **M** ·
   `agents/player_tactics.py` (+ cache on round log). *The single biggest correctness gap.*
2. **BM25/TF-IDF retrieval + channel-separation fix + chain-node anchoring** — replace Jaccard; query from
   public hint+chain only, fingerprint from paragraph body. **M** · `agents/player_tactics.py`, `game/corpus.py`.
3. **Deterministic Judge answer-key oracle** (replace ship-whole-paragraph + all-zeros). **M** ·
   `agents/judge.py` (+ `agents/judge_answerkey.py`).
4. **Outbound leak-guard chokepoint + schema-only answers** wired into judge/gatekeeper. **M** ·
   `game/leakguard.py`, `shared/gatekeeper.py`, `mcp/judge_server.py`.
5. **Per-round/per-match try/except isolation + shot-clock with deterministic fallback + NEVER-THROW floor.**
   **M** · `sdk/sdk.py`, `shared/gatekeeper.py`, `agents/player.py`.
6. **`game/ev.py` (binary-payoff EV core) + guess-format defense via shared `scoring._norm`.** **S** ·
   `game/ev.py`, `agents/player_tactics.py`, `game/scoring.py`.
7. **Widen `determine_outcome` to carry `questions, answers`** (per architecture_review R5 — currently
   `(guess, spec)` only) so a future "answers graded" rule is a one-function edit. **S** · `game/scoring.py`,
   `sdk/sdk.py`.

### P1 — robustness, infra, and the rank-compounding meta layer
8. **Commit-reveal integrity** (publish + wire verification). **S** · `shared/commit.py`, `mcp/client.py`,
   `mcp/judge_server.py`.
9. **Versioned schema-validated MCP contract + tolerant range-validating answer ingestion.** **M** ·
   `mcp/contract.py`, `agents/protocol.py`.
10. **Ollama JSON mode + bounded num_predict/num_ctx + `_extract_json` hardening + warm-pool.** **S** ·
    `shared/ollama_client.py`, `agents/protocol.py`.
11. **Persistent prompt cache + cost/latency ledger.** **M** · `shared/cache.py`, `shared/cost.py`.
12. **Corpus-grounded option synthesis + greedy submodular selection + type-quota enforcement + calibration
    probes.** **L** · `agents/player_tactics.py`, `agents/protocol.py`.
13. **Injection filter + regen loop + deterministic template-chain fallback + player-favoring adjudication +
    mid-quantile selection + judge-server contract hardening/idempotency.** **M** · `agents/judge.py`,
    `game/scoring.py`, `mcp/judge_server.py`.
14. **Opponent modeling + replay/repeat exploit + per-opponent ε.** **M** · `analytics/opponents.json`,
    `agents/player_tactics.py`.
15. **Adversarial opponent test pack + Devil's-Judge regression corpus + replay-from-seed + dual-path consistency
    oracle.** **M** · `tests/adversarial/`.

### P2 — creativity/grade differentiators + tuning
16. **Self-play tuning harness + optimizer → `question_bank.tuned.json`.** **L** · `tuning/`.
17. **Per-question info-gain analytics + Monte-Carlo league simulator + ELO.** **M** · `analytics/`.
18. **Standings + replay web UI + fairness certificate + commentary agent.** **M** · `ui/`,
    `agents/commentator.py`.
19. **Local-embedding re-rank/adjudication + cross-model agreement + model ladder.** **M** ·
    `shared/embed_client.py`, `agents/`.
20. **Offline distillation + online per-opponent bandit.** **L** · `tuning/`.

---

## 10. Assumptions & open rule-questions

- **Scoring grid:** assumed live `win=3, tie=1, loss=1, judge=+2` (`constants.SCORE` / `config/setup.json`).
  **Player payoff is therefore BINARY (tie==loss).** All EV logic reads the grid from config, so if the brief
  finalizes tie>loss (e.g. loss=0), `game/ev.py:should_gamble` flips to hedge-for-tie automatically — no code
  change. **Confirm with the lecturer.**
- **Guess outcome rule:** assumed "both → WIN, one → TIE, none → LOSS." Isolated in `determine_outcome` (widen
  its signature per action #7).
- **Corpus source:** assumed shared + readable by the Player (the entire retrieval thesis depends on this). If
  the league corpus is private, fall back to our bundled copy + any shared index; retrieval degrades to
  hint/chain matching but the Bayesian update still applies. **Confirm corpus distribution.**
- **Are the 20 answers themselves graded?** Open (`scoring.grade_answers` flag reserved). Doesn't change the
  player/judge architecture.
- **Whether the hint is corpus-shipped or LLM-regenerated:** assumed **LLM regenerates the hint, ground-truth
  word/sentence come from the corpus record** (architecture_review R1). This is why the channel-separation fix
  (action #2) matters — never match against the stored hint.
- **League pairing + role counts + inter-group MCP handshake + deadline:** TBD; all isolated behind
  `config/setup.json:league` and the `mcp/contract.py` seam. Agree the contract byte-for-byte with other groups
  early.
- **Undetermined-default policy:** declare index-0 (or chosen default) publicly in the README so it isn't an
  exploitable side-channel.

---

**Summary:** Win at $0 by treating q20 as a closed-set retrieval problem solved by a deterministic core, with the
LLM as a fail-safe fluency layer. Player payoff is binary, so optimize P(both-correct): bank the near-free word
and spend everything on opening-sentence retrieval — wired through a partition oracle + soft Bayesian update that
actually consumes the 20 answers (the #1 fix the code is missing). Make the Judge's +2 unloseable via a
deterministic answer-key, leak-guard, and commit-reveal. Protect every point with try/except isolation, a
shot-clock, and a never-throw deterministic floor. Compound rank with opponent modeling and offline self-play,
and back every claim with analytics, a league Monte-Carlo, and adversarial tests for the creativity/excellence
rubric.

**P0 actions: 7.**

---

## Feasibility & rule-compliance review

> Adversarial pass (28 Jun 2026) over every recommendation above, checked against the **actual** code in
> `src/q20` and `config/setup.json`. Verdict per item: (a) within the rules, (b) truly $0/local, (c) feasible
> against today's codebase. Verified claims are kept; inaccurate ones are corrected here rather than silently.

### A. Code-claim accuracy audit (what §1 asserts vs what the source actually says)
- **CONFIRMED — `best_guess` throws away `qa`.** `agents/player_tactics.py:56` is literally
  `def best_guess(view, corpus, qa, cfg=None):  # noqa: ARG001` and never reads `qa`. This is the real #1 gap.
- **CONFIRMED — channel-mixing retrieval.** `_cand_tokens` (line 38) folds `p.hint + p.associative_word +
  p.paragraph + chain` into the candidate fingerprint; `_similarity` is plain Jaccard (line 24). The
  channel-separation fix is correct and needed.
- **CONFIRMED — judge all-zeros fallback.** `agents/judge.py:49-52` returns `[0 for _ in questions]` on any
  exception. Real systematic index-0 bias.
- **CONFIRMED — no isolation / no shot-clock.** `sdk/run_round` (sdk.py:28) and `run_league` (line 81) have **no
  try/except**; `Gatekeeper.execute` (gatekeeper.py:73) does rate-limit + retry but has **no time budget**. Both
  fixes are feasible.
- **CONFIRMED — narrow scoring seam.** `game/scoring.py:determine_outcome(guess, spec)` (line 26) does **not**
  carry `questions/answers`. P0 #7 (widen signature) is valid and matches architecture_review R5.
- **CORRECTED — the "declared but dead config knobs" claim is wrong.** §1 says `judge_noise, candidate_pool,
  prior_floor, question_quota, min_margin` are "declared but dead." In the **real** `config/setup.json` the
  `player` block is only `{shared_corpus, prior_floor, use_answers}`. So **only `prior_floor` exists** (and it
  *is* wired, player_tactics.py:48-49); `use_answers`/`shared_corpus` exist but are unread; **all the rest must be
  ADDED, not merely wired.** Restate the rubric line as: "wire `use_answers`/`shared_corpus`, and add the new
  tuning knobs as we implement them" — do not claim pre-existing dead knobs we don't have.
- **CORRECTED — `_extract_json` is not the pure-greedy bug described in §4.** `agents/protocol.py:18` tries
  `json.loads(text)` **first**, then falls back to regex `\{.*\}|\[.*\]` (DOTALL). The greedy-to-last-brace
  concern only applies to the fallback branch, and trailing-prose capture is already avoided for clean JSON. The
  hardening (brace-balanced / `raw_decode` + fenced-block strip) is still a *nice* robustness win but is **P2, not
  the every-edge crisis §4 implies.** Downgrade.
- **CORRECTED — config key paths.** Scoring lives at `game.scoring` (not top-level `scoring`); counts are
  `game.questions`/`game.options` (not `num_questions`/`num_options`); corpus source value is `"bundled"` (not
  `"json"`). `game/ev.py` and every config read MUST use these real keys or they silently fall back to defaults.
- **PARTIALLY PRE-EXISTING — leak-guard / commit-reveal.** `mcp/judge_server.py` already publishes only
  `public_view()` (hint+chain) and gates `reveal()` behind `commit_guess()`. So a *structural* leak boundary
  exists; what's missing is (i) a **content scan** of the hint/chain text, and (ii) a **sha256 pre-commit**
  published before questions. Both are additive and free. Keep, but scope as "add content-scan + hash," not
  "build leak-guard from scratch."

### B. Rejected / risky ideas (and why)
- **RISKY (the load-bearing assumption) — "the corpus is shared → retrieval wins."** This is the entire player
  thesis, but the code retrieves from the player's **own local `BundledCorpus`**; over MCP the opponent Judge
  draws from **its** corpus. If the league corpus is not byte-identical across groups, `best_guess` returns the
  wrong paragraph's opening sentence and **the whole retrieval edge collapses to noise.** §10 lists this as a mild
  "confirm" — it is actually the #1 project risk. **Action: confirm the shared-corpus rule with Dr. Segal in
  writing BEFORE investing in BM25/embeddings; gate the retrieval path on `player.shared_corpus` (already in
  config) with the LLM-from-hint path as the live fallback when false.** Still rule-safe and free either way.
- **RULE-RISK — "calibration probes to measure opponent reliability" + "opponent modeling from public logs."**
  Both are fine *only if* they use genuinely public artifacts (the hint/chain and the answers we legitimately
  received). They become a **leak/cheating** problem if "scouting" ever reads another group's secret corpus
  record, private logs, or repo. **Keep, but constrain to public-channel data only and say so explicitly in the
  README** so it can't be read as probing private state.
- **RULE-RISK — "replay/repeat exploit: cache solved (opponent, hint-hash → sentence+word)."** Legitimate as
  *memoization of our own past solves*. It must NOT cache anything obtained outside normal play. Safe with that
  fence; flag in code comments.
- **DEFER (not free-at-match-time-risk, but cost-of-effort) — local embeddings (`nomic-embed-text`) and the
  cross-model / self-consistency k=3 voting.** All $0 and local, so rule-compliant, BUT: embeddings need a ~270MB
  model pull and add a dependency surface; k=3 voting triples latency and fights the shot-clock on a 12GB laptop.
  **Not P0.** BM25/TF-IDF over the shared corpus already wins if the corpus is shared; ship that first, add
  embeddings only if measured retrieval accuracy demands it. Keep both **off by default in config + CI.**
- **DEFER — offline 14b "distillation" and the online per-opponent bandit (§8).** Free and legal, strong
  creativity story, but high effort and only meaningful after the deterministic core + a real league exist.
  Strictly P2; don't let them displace correctness work.
- **NO CHANGE NEEDED vs the "shot-clock forfeit" framing.** Correct and important, but note the local-Ollama
  client already uses a 600s socket timeout; the missing piece is a *budget* that pre-empts the LLM and emits the
  deterministic answer. Feasible, P0.

### C. Confirmed-safe P0 set (all within rules, all $0/local, all feasible today)
1. **Make `best_guess` consume `qa`** — `f_q` partition oracle + soft Bayesian update, with `prior_floor`
   backstop so no single answer zeroes the truth. (player_tactics.py) *Biggest correctness gap, verified.*
2. **BM25/TF-IDF retrieval + channel separation + chain-tail anchoring** — query from public hint+chain only,
   fingerprint from paragraph body only. **Gate on `player.shared_corpus`; LLM-from-hint fallback when false.**
3. **Deterministic Judge answer-key oracle** replacing ship-whole-paragraph + all-zeros, removing the index-0
   bias and the fairness-appeal surface. (judge.py / new judge_answerkey.py)
4. **Per-round + per-match try/except isolation + a Gatekeeper time-budget + NEVER-THROW deterministic floor** —
   a flaky/slow model degrades to deterministic-but-on-time, never forfeits a sweep. (sdk.py, gatekeeper.py)
5. **Widen `determine_outcome` to `(guess, spec, questions, answers, cfg)`** keeping the body unchanged — makes a
   future "answers graded" rule a one-function edit (matches architecture_review R5). (scoring.py, sdk.py)
6. **`game/ev.py` config-driven EV core reading the REAL `game.scoring` keys** + guess-format defense reusing
   `scoring._norm` so we never throw a correct guess on punctuation/casing. (binary-payoff aware.)
7. **Add the new tuning knobs to `config/setup.json:player`** (`judge_noise`, `candidate_pool`, `min_margin`,
   `chain_tail_weight`, `use_embeddings:false`) and wire the already-present `use_answers`/`shared_corpus`. This
   is what actually backs the "zero hardcoding" rubric claim — they do **not** exist yet.

### D. The 5 highest-ROI actions to do FIRST (in order)
1. **CONFIRM the shared-corpus + exact-guess-scoring rules with Dr. Segal (email/Moodle), in writing.** Zero
   code, but it decides whether P0 #2 is a 3-point machine or dead weight. Everything else is hedged behind
   config, so this single answer de-risks the most expensive build.
2. **`best_guess` consumes `qa` (P0 #1).** The one change that makes 20 questions matter; pure, unit-testable,
   no model, immediate win-rate impact.
3. **BM25/TF-IDF + channel-separation retrieval, gated on `shared_corpus` (P0 #2).** The core player edge; ship
   behind the gate so it's safe even if rule (1) comes back "not shared."
4. **Robustness floor: try/except isolation + Gatekeeper time-budget + never-throw deterministic guess (P0 #4).**
   Converts our biggest free-model liability (timeout/crash forfeit) into at-worst-deterministic — protects every
   point already on the board.
5. **Deterministic Judge answer-key oracle (P0 #3).** Kills the index-0 bias, makes the +2 unimpeachable on
   appeal, and is fully CI-testable with no model.

**VERDICT:** The strategy is **sound and almost entirely rule-safe + free.** Three substantive corrections:
(i) the "dead config knobs" claim is inaccurate — those knobs mostly don't exist and must be *added*;
(ii) `_extract_json` hardening is P2, not a §4 crisis; (iii) the shared-corpus assumption is the project's
**#1 risk**, not a footnote — confirm it before building retrieval, and gate the retrieval path on the existing
`player.shared_corpus` flag with the LLM fallback live. No idea was found to be cheating, paid, or infeasible;
the riskier "scouting/replay" ideas are safe once fenced to public-channel data only. With those fixes the P0
set stands at **7**, led by the 5 actions above.
