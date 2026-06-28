# strategy_player.md — the PLAYER agent's winning strategy

> Goal: **top the q20 league as the Player**. The Player reads the Judge's `hint` + `chain`, fires **20
> multiple-choice questions** (4 options each) in **one batch**, then guesses the paragraph's **opening
> sentence** + the **associative word**. Win = both correct (3 pts); tie = one (1 pt); loss = none (1 pt).
>
> This doc is the design contract for `agents/player.py`, `agents/player_tactics.py` (pure, unit-tested) and
> the prompt builders in `agents/protocol.py`. It mirrors the HW6 brain pattern: **LLM at the edges, a
> deterministic engine in the middle, a FakePlayer that runs the whole pipeline with no model/network.**
> Everything tunable lives in `config/setup.json:player` — **zero hardcoded params**.

---

## 0. Design stance (carried from HW6, what scored)

- **Perceive → decode → believe → ask → reason → guess.** The LLM only *writes language* (question text,
  association reasoning). Every numeric decision (which slots to spend, candidate ranking, the final pick) is a
  **pure function** in `player_tactics.py`, fully testable with no LLM.
- **Deterministic fallback at every edge.** Each LLM call is wrapped by the gatekeeper with a shot-clock
  (HW6 `brain.py` pattern). On timeout / malformed JSON / empty reply, the Player degrades to a deterministic
  template, never crashes a round. `FakePlayer` *is* that fallback path — so CI exercises the full pipeline.
- **One batch, no feedback loop.** The 20 questions are sent together and answered together (PRD §3). So the
  Player must **pre-plan an information-maximizing question set**, not adapt mid-stream. This is the crux.

---

## 1. The two targets and what "disambiguate" means

The Player must recover two things:

1. **`opening_sentence`** — the first sentence of the hidden paragraph (a *retrieval* problem: which paragraph
   in the corpus is the Judge holding?).
2. **`associative_word`** — the final node of the Judge's chain `MCP → stream → flow → communication`, i.e.
   the *concept the chain converges on* (a *semantic-inference* problem from the published `hint` + `chain`).

These decompose cleanly:

- **Word target** is largely solvable from the **published hint + chain alone** — the chain is literally a
  breadcrumb trail to it. Questions mostly *confirm* it.
- **Sentence target** needs **discrimination among corpus paragraphs**. This is where the 20 questions earn
  their keep: each question is a probe that splits the candidate set.

The Player keeps an explicit **belief = a probability distribution over corpus paragraphs** (a `CandidateSet`,
analogous to HW6's `BeliefTracker`), updated by the 20 answers.

---

## 2. Phase A — seed the belief from hint + chain (before any question)

The Player has read access to the **same corpus** (PRD §6: pluggable `Corpus`; if the league corpus is
private the Player still has its bundled copy + any shared index). On receiving `RoundSpec.published =
{hint, chain}`:

1. **Build the candidate set.** Score every corpus paragraph by similarity to `hint ∪ chain`:
   - Deterministic core (no LLM, always available): **token/lemma overlap + TF-IDF cosine** between the
     `hint + chain` bag-of-words and each paragraph, plus a bonus if any **chain node appears verbatim** in the
     paragraph. This is the seed prior `P0(paragraph)`.
   - Optional LLM refinement: embed hint+chain and paragraphs via the Ollama embedding model and re-rank by
     cosine. Gated, with the TF-IDF score as the fallback if embeddings are unavailable.
2. **Normalize to a prior** over the top-K candidates (`K = config player.candidate_pool`, e.g. 24). Keep the
   long tail at a small floor so a tricky Judge can't fully hide a paragraph the seed under-rated.
3. **Infer the word target** from the chain: the associative word is the chain's **last node** (or the concept
   it points to). The Player drafts a **ranked word hypothesis list** (top node + 2–3 near-synonyms/parents),
   each used to bias both questions and the final guess. The chain direction matters: `A→B→C→word` means the
   word is the *destination*, so weight the **tail** nodes far more than the head.

> Why this matters for scoring: getting the word right is *cheap* (it's published) and converts a loss into a
> tie or a tie into a win. The strategy **never under-invests** in the word.

---

## 3. Phase B — choosing the 20 questions (information-gain framing)

This is the heart. We treat each MCQ as a **measurement** that partitions the candidate set, and we pick the
batch that **maximizes expected information** about the hidden paragraph, subject to: questions are sent
*before* any answer, so the set must be **jointly** informative, not greedily-then-adaptively informative.

### 3.1 Question types (a typed toolbox, each a pure generator)

Every question is `MCQ{q: str, options: [4]}` with **exactly one option the true paragraph satisfies**. Types,
ordered by typical discriminative power:

| Type | Probe | Example options |
|---|---|---|
| **Topic/category** | which domain | "What is the paragraph mainly about?" → [technology, biology, history, sports] |
| **Entity presence** | does a salient entity appear | "Which of these is mentioned?" → [Kafka, mitochondria, the Senate, none] |
| **Lexical/feature** | surface features of the *opening sentence* | "The first sentence begins with…" → [a name, a number, "The", a question] |
| **Length/structure** | paragraph shape | "Roughly how long is the paragraph?" → [<40 words, 40–80, 80–150, >150] |
| **Stance/sentiment** | tone | [neutral/expository, positive, critical, narrative] |
| **Chain-anchored** | confirm the associative word | "Which concept best fits the hint chain's destination?" → [w1, w2, w3, w4] |

Each generator is pure: given the current `CandidateSet`, it proposes the *single question of its type that
best splits the candidates* and computes that split.

### 3.2 The selection objective — entropy reduction (deterministic core)

For a candidate distribution `P` over paragraphs and a question `q` with options `o ∈ {1..4}`, define the
**partition** `f_q(paragraph) → option` (which option the true paragraph would make the Judge pick). Expected
posterior entropy if we ask `q`:

```
H(P)                = -Σ P(c) log P(c)
P(option o | q)     =  Σ_{c : f_q(c)=o} P(c)
H(P | q)            = -Σ_o P(o|q) · Σ_{c:f_q(c)=o} (P(c)/P(o|q)) log(P(c)/P(o|q))
InfoGain(q)         =  H(P) - H(P | q)
```

We want the **batch** of 20 maximizing joint info gain. True joint optimization is exponential, so use the
proven **greedy + diversity** approximation (submodular set-cover style):

1. Generate a **pool** of candidate questions (all types, several phrasings each).
2. **Greedily pick** the question with the highest *marginal* InfoGain **given the partitions already chosen**
   (i.e. condition on the chosen questions' joint partition). This naturally avoids redundant questions: once a
   "topic" split is chosen, a second near-identical topic split has near-zero marginal gain.
3. Enforce a **type quota** from config (`player.question_quota`, e.g. `{topic:3, entity:6, lexical:4,
   structure:2, stance:2, chain:3}`) so the batch is balanced and robust if one type is sabotaged.
4. **Reserve ≥3 chain-anchored questions** to pin the associative word (see §2).

This is a one-shot batch design (no mid-round feedback), so we optimize **expected** entropy under the prior
`P0` — exactly the right framing for a single simultaneous measurement.

### 3.3 Discriminating power = balanced 4-way splits

A question is maximally informative when each of its 4 options is satisfied by **~25% of candidate
probability** (a balanced 4-way split → up to **2 bits** per question; 20 such *independent* questions cover
2^40 ≫ any corpus). The generators therefore **choose option thresholds to balance the split** over the
*current* candidates — e.g. the length question's bucket edges are set at the candidates' quartiles, not fixed
word counts. This is why bucket edges are **data-driven, not hardcoded**.

### 3.4 Question hygiene (so the Judge can actually answer)

- **Mutually exclusive, collectively exhaustive options**, always including a safe **"none of these"** so a
  truthful Judge is never forced to lie (which would corrupt our inference).
- **Grounded in observable paragraph facts** (entity present? length? opening word?) — not subjective trivia
  the Judge could answer either way.
- Phrased by the LLM for fluency but the **option set + the partition come from the deterministic generator**,
  so we always know `f_q` for inference. The LLM never invents options unsupervised.

---

## 4. Phase C — reasoning from the 20 answers to the guess

The Judge returns `[20 × chosen_option]`. The Player updates belief by **Bayesian filtering** over candidates:

```
for each paragraph c in CandidateSet:
    score(c) = log P0(c) + Σ_i [ match(answer_i, f_{q_i}(c)) ? log(1-ε) : log(ε) ]
```

- `f_{q_i}(c)` = the option the paragraph *c* implies for question *i* (known, computed at generation time and
  cached on the round log).
- `ε` (`player.judge_noise`, e.g. 0.1) = the assumed probability the Judge answered "off" — a **soft** update
  so a single surprising/adversarial answer doesn't zero out the true paragraph. This is the robustness knob.
- The posterior is `softmax(score)`. **`opening_sentence` guess = first sentence of `argmax` paragraph.**

For the **associative word**: combine (a) the chain-derived hypothesis list (§2) with (b) the answers to the
**chain-anchored questions**. The word guess = the hypothesis with the most answer-support; if the Judge's
chain answers contradict the seed top-1, switch to the supported one. An LLM pass can paraphrase to the
canonical form, but the **deterministic ranked list is the source of truth** (fallback when LLM is down).

### 4.1 Opening-sentence normalization
The guess must match how the Judge stores it. Normalize both sides before the Player commits: trim, collapse
whitespace, strip trailing punctuation, lowercase for the internal confidence check (the *emitted* guess keeps
original casing). Scoring exactness is the Referee's job — we just maximize the chance of an exact/near match.

---

## 5. Robustness to a tricky Judge

A Judge that wants to deny the win (Judge always gets +2, so it's mildly adversarial) can: pick an obscure
paragraph, write a misleading hint, answer ambiguously, or exploit "none of these".

Defenses, all already in the design:

- **Soft Bayesian update (`ε`)** — no single answer can eliminate the true candidate; we tolerate a liar.
- **Type diversity + quotas** — if the Judge games one question type (e.g. always picks "none"), the other
  types still carry signal. We **down-weight a question type** whose answers are statistically inconsistent
  with *every* high-prior candidate (likely a sabotaged/ambiguous probe).
- **Probability floor on the tail** — the seed never fully discards a paragraph, so a deliberately misleading
  hint can't make the true paragraph unreachable.
- **Chain redundancy** — multiple chain-anchored questions + the published chain itself triangulate the word;
  one bad answer doesn't sink it.
- **"None of these" sanity** — if a Judge answers "none" to a question whose options provably cover all
  candidates, that answer is flagged low-trust and contributes near-zero to the update.
- **Self-consistency across answers** — if answers imply *no* single paragraph (all candidates fit ≤k answers),
  fall back to the **seed argmax** (the hint-based retrieval), which the Judge can't fully corrupt.

---

## 6. Self-check before guessing (a pre-commit gate)

Before emitting the final guess, run a deterministic `confidence_report` (pure function, logged):

1. **Margin check** — is `P(top1) / P(top2) ≥ player.min_margin` (e.g. 1.5)? If not, the answers were
   under-discriminating; **back off to the seed-prior argmax** (hint retrieval is usually more reliable than a
   noisy answer set) and lower confidence.
2. **Coverage check** — does the top paragraph **match a strong majority** of the 20 answers
   (`≥ player.min_answer_match`, e.g. 0.7)? If a "winning" candidate contradicts many answers, it's suspect →
   re-rank excluding the most-violated answers, re-check.
3. **Word/sentence coherence** — does the guessed associative word plausibly relate to the guessed paragraph
   (token overlap or embedding similarity above a floor)? A mismatch suggests we picked the wrong paragraph
   *or* the wrong word; prefer the pair with the higher joint score.
4. **Format/leak guard** — opening sentence is non-empty, is an actual first sentence (ends at first
   terminator), and the word is a single concept token/short phrase. Normalize per §4.1.
5. **Tie-aware hedging** — because **tie still beats loss** (1 vs 1 here, but a tie denies the Judge nothing
   extra and a *win* is +3), when sentence confidence is low but word confidence is high, **never sacrifice the
   word**: lock the high-confidence word, spend remaining reasoning budget on the sentence. The scoring grid is
   read from config so this trade adapts if rules change.

The report is attached to the round log (auditable, like HW6's turn records) and drives whether we emit the
LLM-refined guess or the deterministic fallback.

---

## 7. LLM vs deterministic split (implementation map)

| Step | Deterministic (always runs, = FakePlayer) | LLM (gated, refines, can fail safely) |
|---|---|---|
| Seed prior | TF-IDF / overlap over corpus | embedding re-rank |
| Word hypothesis | chain tail + synonym table | paraphrase to canonical word |
| Question pool | typed generators + entropy split | natural-language phrasing of `q` |
| Batch selection | greedy submodular InfoGain + quotas | — (kept deterministic for auditability) |
| Answer → belief | soft Bayesian filter | — |
| Final guess | argmax paragraph + ranked word | rewrite opening sentence to match style |
| Self-check | `confidence_report` | — |

If **every** LLM call fails, `FakePlayer` still produces a fully-scored, often-winning guess from the
deterministic core alone. This guarantees a CI-green, network-free end-to-end round (plan.md §"runnable").

---

## 8. Config surface (`config/setup.json:player`) — zero hardcoding

```jsonc
"player": {
  "n_questions": 20,
  "n_options": 4,
  "candidate_pool": 24,
  "question_quota": { "topic":3, "entity":6, "lexical":4, "structure":2, "stance":2, "chain":3 },
  "judge_noise": 0.10,          // ε in the Bayesian update (tricky-judge tolerance)
  "prior_floor": 0.01,          // tail probability floor
  "min_margin": 1.5,            // self-check top1/top2 ratio
  "min_answer_match": 0.70,     // self-check coverage
  "chain_tail_weight": 2.0,     // weight last chain nodes over head
  "use_embeddings": true,       // gracefully off if Ollama embed model absent
  "shot_clock_seconds": 60
}
```

All thresholds, quotas, and counts are config — so a rule change (e.g. 15 questions, 3 options, different
scoring grid) is a config edit, not a code change, satisfying the "swappable rules behind interfaces" mandate.

---

## 9. Why this tops the league (summary of edge)

1. **Information-theoretic batch design** — balanced 4-way splits chosen to maximize *joint* entropy reduction
   extract near the theoretical max (~2 bits/question) from a one-shot batch most naive players waste on
   redundant or unanswerable questions.
2. **The word is nearly free** and we never drop it — converting losses→ties and ties→wins on scoring.
3. **Adversary-robust** soft Bayesian inference + probability floor + type quotas survive a hostile Judge.
4. **A self-check gate** prevents low-confidence over-commitment, backing off to reliable hint-retrieval.
5. **Fully deterministic core** = reproducible, debuggable, CI-safe, and independent of flaky local-model
   quality — the exact lesson that scored in HW5/HW6.
