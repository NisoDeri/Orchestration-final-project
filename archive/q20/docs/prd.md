# PRD — `q20`: a "20 Questions" multi-agent league

**Group nis-yar1 · Orchestration of AI Agents (Dr. Yoram Segal) · Final project (40%)**

> Status: **DRAFT v0.1** — built from the syllabus brief. Game-rule specifics marked **[TBD-confirm]** are
> isolated behind `config/` + small pure modules so finalizing them is a config edit, not a rewrite.

## 1. Problem & goal
Build two autonomous agents — a **Judge** and a **Player** — that play a **"20 Questions"** word/association
game and compete in a **multi-round inter-group league**. The graded value (per the course's recurring theme)
is the **orchestration**: agents coordinating in natural language over **MCP**, turning language into action,
under a provably-fair referee — not raw game outcome. Target: a working, league-ready, professionally-built
system that ranks high.

## 2. Players & roles
| Agent | Responsibility |
|---|---|
| **Judge** | pick a paragraph from the corpus; emit a **hint** + **associative-word chain**; answer the player's 20 questions; **adjudicate** the player's guesses; never leak the answer. |
| **Player** | read hint+chain; emit **20 multiple-choice questions** (4 options each) in one batch; from the answers, **guess** the opening sentence + the associative word. |
| **Referee** (engine, not an LLM) | enforce the protocol + **deterministic scoring**; the single source of truth. |

## 3. Game loop (one match = Judge vs Player)
```
Judge.select_paragraph(corpus) -> RoundSpec{paragraph, opening_sentence, associative_word, hint, chain}
Judge.publish(hint, chain)            # the answer (paragraph/sentence/word) stays hidden (leak-guard)
Player.ask() -> [20 x MCQ{q, options[4]}]
Judge.answer(questions) -> [20 x choice]
Player.guess(answers) -> {opening_sentence, associative_word}
Referee.score(guess, RoundSpec) -> Outcome{result, points{player, judge}}
```

## 4. Scoring (config-driven — `config/setup.json:scoring`) **[TBD-confirm]**
Defaults from the brief: **win 3 · tie 1 (each) · loss 1 · judge +2**. Provisional outcome rule (one pure
function, `game/scoring.py:determine_outcome`, easy to swap): player **wins** if it gets **both** the opening
sentence and the associative word; **tie** if exactly one; **loss** if none. Judge always **+2**.

## 5. League (config-driven — `config/setup.json:league`)
Round-robin over groups; each group is **player ~4×** and **judge ~2×** (`rounds`, `roles_per_group`).
Standings accumulate points; rank → grade (1st≈100 … last≈70). Inter-group play runs **over MCP** (same
bridge pattern as the HW6 bonus — local for dev, ngrok/login for the live league). **[TBD-confirm pairing]**

## 6. Corpus (`game/corpus.py`) **[TBD-confirm source]**
Pluggable `Corpus` interface: `sample() -> Paragraph`. Ships a small bundled `data/corpus.sample.json`;
swappable for the provided dataset / Wikipedia / arXiv via config without touching game logic.

## 7. Tech & constraints (from the brief)
- **CLI-only** workflow; **Login not API key**; we run **local Ollama** (qwen2.5 / aya) — **$0, no key**.
- **Vibe-Coding lifecycle** with `prd.md` / `plan.md` / `todo.md` (500–1000 tasks).
- Engineering bar (carried from our HWs): every `src/` file **≤150 lines**, **ruff** clean, **pytest ≥85%**,
  GitHub Actions CI, lazy heavy imports, zero hardcoded params (all in `config/`).
- **MCP** transport via FastMCP (reused from HW6); LLM via a gatekept Ollama client.

## 8. Deliverables
GitHub repo with: the two agents + referee + league runner + MCP servers; `config/`; bundled sample corpus;
`prd.md`/`plan.md`/`todo.md`; rich README (rules, architecture, how-to-run, how-to-join-the-league); tests +
CI; a web replay/standings UI (stretch, reusing the HW6 UI pattern). Each member submits the Moodle PDF.

## 9. Success criteria
A full match runs end-to-end on local models (Judge↔Player over MCP); the referee scores deterministically;
a league of N groups produces standings; ruff/tests/CI green; ≤150-line files; rules are swappable via config.

## 10. Risks & mitigations
- **Rules still partial** → everything rule-specific is config + a pure function; confirmed details slot in.
- **Inter-group interop** → agree a shared MCP tool contract early (we have the HW6 contract as a template).
- **Local-model quality** → keep the LLM for language/association, deterministic engine for scoring (HW6 lesson).
- **Corpus access/licensing** → bundle a sample; make the source pluggable.
