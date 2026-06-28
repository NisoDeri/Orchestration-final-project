# architecture_review.md — hardening pass on `q20`

**Group nis-yar1 · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

> Input: [`prd.md`](prd.md) v0.1 + [`plan.md`](plan.md), cross-checked against the proven HW6 stack
> (`hw6/src/mcp_cops/{shared,game,agents,sdk,mcp}`). This review locks module boundaries, pins the two
> TBD seams (corpus, scoring) behind concrete signatures, defines the full `config/` schema, marks the
> exact LLM/deterministic line, and lists the gaps to close before coding. Everything below is meant to
> be copy-pasted into `todo.md` tasks — no further design decisions should be needed to start the build.

---

## 0. Verdict & the 6 things to change now

The PRD/plan are directionally right and the HW6 reuse story holds. But four ambiguities will cause churn
if not nailed before phase 2:

1. **`RoundSpec` is referenced but never typed.** It crosses every layer (judge→engine→player→referee→log).
   Define it as a frozen dataclass *now* (§2) — it is the spine of the system.
2. **The MCP tool contract is hand-waved ("reuse the HW6 bridge").** HW6's tools are `observe/legal_steps/
   apply/scores` — q20 needs a *different* verb set (`publish/ask/answer/guess`). Pin it now (§6) because it
   is the inter-group interop contract and the one thing two groups must agree on byte-for-byte.
3. **The leak-guard is a stated requirement with no enforcement point.** "Judge never leaks the answer" must
   be a referee invariant, not a prompt politeness. Put it in `game/round.py` (§4).
4. **Scoring `determine_outcome` signature in the PRD (`guess, spec, cfg`) loses the per-question answers** —
   you cannot implement a future "answers graded for correctness" rule (initial.md open Q) without them.
   Widen the signature now (§3) so the seam survives rule confirmation.
5. **`game/round.py` is doing two jobs** (state container + flow). Split flow into the SDK; keep `round.py`
   a pure data+validation module (§1) or it will blow the 150-line cap once leak-guard + MCQ validation land.
6. **Determinism of the engine depends on a seed that the PRD never threads.** Every `sample()`, every
   tie-break, every league pairing must take an injected `random.Random` (HW6 does this; PRD/plan omit it).
   Make `seed` a first-class config key and thread it (§5, §8).

---

## 1. Module boundaries (locked)

Mirror HW6's layering exactly; only the domain nouns change. Package = `q20`, `PYTHONPATH=src`.

```
cli/main.py        thin: play-round | run-league | serve {judge|player} | report     -> SDK only
 └ sdk/sdk.py      ONLY orchestrator: run_round, run_league, assemble_round_log, get_report
     ├ agents/     protocol.py (prompt builders + tolerant parsers, NO i/o)
     │             judge_brain.py · player_brain.py (LLM; thin take_* methods)
     │             fake.py (FakeJudge/FakePlayer — deterministic) · factory.py (live/fake builders)
     │             personas.py (persona strings — keep out of factory so it stays <150)
     ├ game/       corpus.py (Corpus interface + JsonCorpus)  ── SEAM 1
     │             round.py   (RoundSpec, MCQ, Answer, Guess dataclasses + validation; pure)
     │             scoring.py (determine_outcome — pure)        ── SEAM 2
     │             league.py  (round-robin schedule + standings accumulation; pure)
     ├ mcp/        judge_server.py · player_server.py · client.py · orchestrator.py · cross.py (lazy fastmcp)
     └ shared/     config · gatekeeper · cost · ollama_client · logger · exceptions · version  (lift from HW6 ~as-is)
constants.py       Role(StrEnum) · Outcome(StrEnum) · Phase(StrEnum) · defaults count guards
config/            setup.json · models.json · rate_limits.json
data/              corpus.sample.json (bundled)
tests/             unit/ + integration/ ;  .github/workflows/ci.yml
```

**Dependency rule (enforce in a test):** `game/*` imports nothing from `agents`, `mcp`, `sdk`, or `shared`
except `constants` + `exceptions`. This is what makes the engine deterministically testable. HW6's
`game/referee.py` already obeys this — keep it.

**150-line watch list** (these *will* overflow if not pre-split):
- `agents/protocol.py` — HW6's is 144 lines with 2 verbs; q20 has 3 prompt builders + 3 parsers. **Split**
  into `protocol_judge.py` + `protocol_player.py`, or keep builders here and parsers in `parsers.py`.
- `sdk/sdk.py` — HW6's is 150 exactly. Move `assemble_round_log` to `sdk/log.py` from day one.
- `game/round.py` — RoundSpec + MCQ/Answer/Guess + validation + leak-guard. Put validation helpers in
  `game/validate.py` if it crosses ~120.

---

## 2. `RoundSpec` and the message types — define these first

The single most important missing artifact. Put in `game/round.py`, frozen dataclasses, `slots=True`:

```python
@dataclass(frozen=True, slots=True)
class RoundSpec:                       # the Judge's secret + public split
    paragraph: str                     # SECRET full paragraph
    opening_sentence: str              # SECRET — what the player must guess
    associative_word: str              # SECRET — the chain's terminal word
    hint: str                          # PUBLIC
    chain: tuple[str, ...]             # PUBLIC associative chain, e.g. ("MCP","stream","flow","communication")
    source_id: str                     # corpus provenance (for the log / audit)

    def public(self) -> "PublicSpec":  # the ONLY thing the player may see (leak-guard)
        return PublicSpec(self.hint, self.chain, self.source_id)

@dataclass(frozen=True, slots=True)
class PublicSpec:
    hint: str; chain: tuple[str, ...]; source_id: str

@dataclass(frozen=True, slots=True)
class MCQ:
    text: str; options: tuple[str, str, str, str]      # exactly 4 (config-driven count, validated)

@dataclass(frozen=True, slots=True)
class Answer:
    index: int                          # 0..3 chosen by judge

@dataclass(frozen=True, slots=True)
class Guess:
    opening_sentence: str; associative_word: str
```

The `public()` projection is the leak-guard's mechanical core: the player layer and MCP `publish` tool may
**only ever** receive `PublicSpec`, never `RoundSpec`. Make this a test: `assert not hasattr(published, "paragraph")`.

---

## 3. SEAM 2 — scoring (pin the signature, keep the rule swappable)

PRD §4 signature `determine_outcome(guess, spec, cfg)` is too narrow. Widen to carry the answers and the
match transcript so *any* of the open scoring variants (initial.md §"answers graded?") slots in later
**without touching callers**:

```python
# game/scoring.py  — PURE, no i/o, fully unit-tested
def determine_outcome(
    guess: Guess,
    spec: RoundSpec,
    questions: tuple[MCQ, ...],
    answers: tuple[Answer, ...],
    cfg: dict,                          # cfg["scoring"] block (see §5)
) -> Outcome:                           # Outcome dataclass: result + points{player, judge}
    ...
```

**Provisional rule (default, documented as swappable):** normalize-and-compare opening sentence and word
(case-fold, strip, collapse whitespace, optional fuzzy ratio threshold from `cfg["scoring"]["match"]`).
- both correct → `WIN` (player), points `cfg.win`
- exactly one → `TIE`, points `cfg.tie` each
- none → `LOSS`, points `cfg.loss`
- judge always gets `cfg.judge_bonus` (+2)

**Adjustments vs PRD:**
- Add a `match` sub-config: `{"mode": "exact|normalized|fuzzy", "fuzzy_threshold": 0.9}`. Without this,
  "the answer was right but capitalized differently" becomes an un-tunable hardcode — exactly the kind of
  thing that cost points on HW1.
- Make `Outcome` a frozen dataclass (not a bare dict) so the league accumulator can't typo a key.
- Keep `questions`/`answers` in the signature even though the default rule ignores them. This is the cheap
  insurance: if the brief later says "+1 per question the judge answered consistently," it is a one-function
  edit. **Mark the unused params with a comment, do NOT drop them** (ruff B/ARG — silence with `# noqa: ARG001`
  and a note, since the seam is intentional).

---

## 4. SEAM 1 — corpus + the leak-guard

```python
# game/corpus.py
class Corpus(Protocol):
    def sample(self, rng: random.Random) -> RoundSpec: ...   # rng INJECTED -> deterministic

class JsonCorpus:                       # ships, reads data/corpus.sample.json
    def __init__(self, path: Path, rng_unused=None): ...
    def sample(self, rng): ...          # pick paragraph, derive opening_sentence, read chain/word from record
```

**Bundled `data/corpus.sample.json` record shape** (so the judge brain has *something* to associate from
and tests are deterministic):

```json
{ "version": "1.00",
  "paragraphs": [
    { "source_id": "mcp-001",
      "paragraph": "MCP is a protocol that lets agents...",
      "opening_sentence": "MCP is a protocol that lets agents communicate.",
      "associative_word": "communication",
      "hint": "a way two programs talk",
      "chain": ["MCP", "stream", "flow", "communication"] }
  ] }
```

**Decision to record:** does the *Judge brain (LLM)* invent the hint+chain, or does the corpus ship them?
Recommend **corpus ships a reference chain/word; the LLM judge may regenerate a hint** (so the LLM has a real
job) but the *associative_word the player must guess* comes from the corpus record — otherwise the referee
has no ground truth to score against and the game is unjudgeable. This is a real gap in the PRD: it implies
the judge "writes" the answer, but then nothing can deterministically score it. **Ground truth must be
data, not model output.**

**Leak-guard (referee invariant, in `game/round.py` or a `game/referee.py`):**
- `publish()` returns only `spec.public()`.
- A `Match`/referee object holds the secret `RoundSpec`; the player-facing surface is a separate object that
  literally does not hold the secret fields. Enforced by the `public()` projection + a test.
- Validate the judge's answers are in `0..len(options)-1`; validate the player sent exactly
  `cfg.num_questions` MCQs each with exactly `cfg.num_options` options. Reject (referee `Verdict`-style)
  rather than crash — mirror HW6's `Verdict(ok, reason)` pattern.

---

## 5. Config schema (complete — `config/setup.json`)

Lift the HW6 three-file pattern verbatim (`shared/config.py` `ConfigLoader` + `validate_config_version`).
Note HW6's `_normalize_game` trick: it bridges the assignment's exact spec key names to internal aliases
from one source of truth — replicate that pattern if the final brief dictates specific key names.

```json
{
  "version": "1.00",
  "project": {
    "name": "q20", "group": "nis-yar1",
    "course": "Orchestration of AI Agents", "lecturer": "Dr. Yoram Segal",
    "authors": ["Nissim Deri", "Yarden Tziar"],
    "github_repo": "https://github.com/NisoDeri/orchestration-final",
    "timezone": "Asia/Jerusalem"
  },
  "game": {
    "num_questions": 20,
    "num_options": 4,
    "seed": 7,
    "answer_time_limit_seconds": 180,
    "on_timeout": "abstain"
  },
  "scoring": {
    "win": 3, "tie": 1, "loss": 1, "judge_bonus": 2,
    "match": { "mode": "normalized", "fuzzy_threshold": 0.9 }
  },
  "corpus": {
    "source": "json",
    "path": "data/corpus.sample.json"
  },
  "league": {
    "rounds": 1,
    "games_as_player": 4,
    "games_as_judge": 2,
    "pairing": "round_robin",
    "tie_break": ["points", "head_to_head", "seed"]
  },
  "servers": { "host": "127.0.0.1", "judge": 8765, "player": 8766 },
  "email": { "to": "rmisegal+uoh26b@gmail.com", "subject": "nis-yar1 — q20 league report" }
}
```

`models.json` / `rate_limits.json`: **copy HW6 unchanged** except agent role names → `judge`, `player`
(plus a `default` fallback — `model_for()` already falls back). Keep `provider: "ollama"`, no API key.

**Rule: nothing in `src/` reads a literal `20`, `4`, `3`, `0.9`, a model name, a port, or a path.** All via
`cfg`. A grep test in CI (`grep -rnE '\b(20|num_questions)\b'`-style guard) is worth adding — HW1 lost points
for stray hardcodes.

---

## 6. MCP tool contract (the interop spine — agree this with other groups EARLY)

HW6's verbs (`observe/legal_steps/apply/scores/send_message/read_inbox`) do **not** map to q20. Define the
q20 contract explicitly. Two servers (judge, player) + a referee role folded into the judge server (the
judge holds the secret + adjudicates — but scoring stays the deterministic `determine_outcome`, the LLM
never scores):

| Tool (server) | Direction | Payload in | Payload out |
|---|---|---|---|
| `start_round` (judge) | orchestrator→judge | `{seed, round_id}` | `{round_id}` |
| `publish` (judge) | player→judge | `{}` | `PublicSpec` (hint, chain, source_id) — **never the secret** |
| `ask` (player) | orchestrator→player | `PublicSpec` | `{questions: [20× MCQ]}` |
| `answer` (judge) | player→judge | `{questions}` | `{answers: [20× index]}` |
| `guess` (player) | orchestrator→player | `{answers}` | `Guess` |
| `adjudicate` (judge) | orchestrator→judge | `{guess, questions, answers}` | `Outcome` (via `determine_outcome`) |

**Keep the in-process path and the over-the-wire path driving the *same* agent methods** — HW6's
`orchestrator.py` reuses `assemble_game_log` + `_first_pos` from `sdk.py` so both paths emit byte-identical
logs. Replicate: `sdk.run_round` (in-process) and `mcp.orchestrator.run_round_over_mcp` both call
`assemble_round_log`. Reuse HW6's `_wait_port`, `start_servers`, subprocess teardown verbatim.

**Validation note (HW6 lesson, line 70 of orchestrator.py):** the verdict/result can lag the authoritative
state by one round-trip. For q20 this is simpler (no turn loop — it's a fixed publish→ask→answer→guess
sequence), which is a *risk reducer*: q20's MCP flow is strictly easier than HW6's. Lean into that.

---

## 7. The LLM / deterministic line (mark it explicitly)

| Concern | Owner | Why |
|---|---|---|
| Pick paragraph, ground-truth opening sentence + associative word | **Corpus (data)** | scorable ground truth must not be model output (§4) |
| Write the hint, optionally rephrase the chain | **LLM (judge)** | gives the judge a real language job |
| Generate 20 MCQs from `PublicSpec` | **LLM (player)** | the player's reasoning |
| Answer 20 MCQs given the secret paragraph | **LLM (judge)** | the judge's reasoning |
| Guess opening sentence + word from answers | **LLM (player)** | the player's payoff reasoning |
| Validate counts/options/indices, leak-guard | **Engine** | invariants, never a prompt |
| `determine_outcome` / standings / pairing | **Engine (pure)** | deterministic, unit-tested, the grade anchor |

`FakeJudge`/`FakePlayer` replace **only** the four LLM rows with deterministic stand-ins (FakeJudge: answers
index 0 or a hash-of-question; FakePlayer: emits templated MCQs and guesses by copying chain terms). They
honor the *exact same* `take_*` method signatures as the real brains — HW6's `FakeAgent` proves the
`take_turn` contract; do the same here so `q20 play-round --fake` runs the whole pipeline with **no model,
no network** (CI gate).

Use HW6's **tolerant-parser pattern** (`protocol.py:_extract_json` + `parse_belief`/`parse_action` never
raise — garbage → safe sentinel). For q20: a malformed MCQ batch → fewer/padded questions (referee rejects
over `Verdict`), a malformed answer → `abstain` (per `on_timeout`), a malformed guess → empty `Guess`
(scores as LOSS). A flaky local model must never crash a league game.

---

## 8. Testability plan (to hit ≥85% cleanly)

- **Pure-engine unit tests carry the coverage** (HW6 did this). `scoring.determine_outcome` (all four
  outcomes × three `match.mode`s), `corpus.sample` (deterministic under fixed `rng`), `round` validation
  (wrong count, wrong option count, out-of-range answer index, leak-guard projection), `league` schedule +
  standings + tie-breaks. These need **no model and no MCP** and are fast.
- **One integration test:** `run_round(FakeJudge, FakePlayer, cfg)` end-to-end → asserts a scored
  `Outcome` + a well-formed log. Mirror HW6's fake-agent integration test.
- **One leak-guard test:** the object handed to the player has no secret attribute.
- **One dependency-direction test:** import `q20.game.*` and assert it pulled in nothing from `agents/mcp/sdk`.
- **MCP path:** keep it behind a `@pytest.mark.slow`/skip-if-no-fastmcp guard (lazy import) so CI green
  without fastmcp installed — HW6 reaches fastmcp only through the lazy `RefereeClient`.
- Thread `seed` from `cfg["game"]["seed"]` into every `random.Random` (corpus sample, league pairing,
  fake-agent choices). Without this the "deterministic engine" claim is false and tests flake.

---

## 9. Risks & gaps to close (prioritized)

| # | Gap / risk | Action | When |
|---|---|---|---|
| R1 | Ground truth = model output makes the game unscorable | Corpus ships `opening_sentence`+`associative_word`; LLM only writes hint/MCQs/answers/guess | **before phase 2** |
| R2 | `RoundSpec`/MCQ/Answer/Guess untyped | Define the §2 dataclasses first | **before phase 2** |
| R3 | Leak-guard is a wish, not a mechanism | `public()` projection + referee holds secret + test | phase 2 |
| R4 | MCP verb set undefined → can't interop | Pin the §6 table; publish it for inter-group agreement | phase 3 (but spec now) |
| R5 | `determine_outcome` signature loses answers | Widen per §3; keep unused params | phase 2 |
| R6 | Matching mode hardcoded | `scoring.match` config block | phase 2 |
| R7 | 150-line overflow in protocol/sdk/round | Pre-split per §1 | each phase |
| R8 | Seed not threaded → nondeterminism | First-class `seed`, inject `rng` everywhere | phase 2 |
| R9 | Open brief items (pairing, exact scoring, corpus source, deadline) | All already isolated behind config/seams — **do not block scaffold**; slot in on confirmation | on confirm |
| R10 | League grade ↔ standings mapping unstated | `league.py` returns standings; grade-mapping is a *report* concern, keep out of engine | phase 5 |

---

## 10. Concrete build-order adjustment

Plan.md phases are fine; tighten phase 2 to front-load the spine:

- **2a (do first):** `constants.py` (Role/Outcome/Phase enums), `game/round.py` dataclasses + validation +
  leak-guard, `game/scoring.py` + its full unit-test matrix. *This is the gradeable deterministic core.*
- **2b:** `game/corpus.py` + `data/corpus.sample.json` + sample-determinism test.
- **2c:** `game/league.py` (pure schedule + standings) + tests.
- **3:** `agents/protocol*.py`, `fake.py` (FakeJudge/FakePlayer), `factory.py`, `personas.py`; `sdk.run_round`
  in-process; the integration test; `q20 play-round --fake` exits 0 with a scored log.
- **4+:** real Ollama brains (after rules confirmed), MCP servers/orchestrator (reuse HW6 wholesale),
  cross-group bridge, UI, harden.

**Definition of done for this hardening (carry into todo.md):** §2 types exist; §3/§4 seams have the pinned
signatures; §5 config validates via the HW6 `ConfigLoader`; §6 MCP table is documented; `play-round --fake`
runs with no model/network; ruff clean; engine coverage ≥85%; every `src/` file ≤150 lines.
