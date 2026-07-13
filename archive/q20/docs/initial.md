# initial.md — free-text idea brief (Vibe-Coding step 1)

**Course:** Orchestration of AI Agents (Dr. Yoram Segal) · **Group:** nis-yar1 (Nissim Deri & Yarden Tziar)
**Weight:** the final project is **40%** of the course grade.

## The idea (as understood from the syllabus brief — some details are TBD, see §"Open questions")

Build a **"20 Questions" league** played by **two autonomous agents per group**:

- a **Judge agent**, and
- a **Player agent**.

Groups compete in a **multi-round league** (each group plays ~**4 games as player** and ~**2 games as
judge**). It is the spiritual successor to HW6 (two agents talking over MCP) — so we reuse that stack.

### One game ("20 Questions")
1. The **Judge** picks an article/paragraph from a **corpus**, and writes/selects a target paragraph inside it.
2. The Judge publishes a **hint** + an **associative-word chain** (the lecturer's example:
   `MCP → "נחל"(stream) → flow → communication`).
3. The **Player** sends **20 multiple-choice questions** ("American format", 4 answers each) in **one batch**.
4. The Judge **answers** the 20 questions; the Player then **guesses** (a) the paragraph's **opening sentence**
   and (b) the **associative word**.
5. **Scoring** (provisional, config-driven): win **3** / tie **1 each** / loss **1**; the **Judge gets 2**.

### Grade mapping (from the brief)
- A working project meeting the basic criteria = **60**.
- League rank sets the rest: **1st ≈ 100**, **last ≈ 70** (subject to change).

## Hard rules from the brief (we already follow these)
- **Terminal/CLI only** — no Cursor/Copilot/Gravity integration (we use Claude Code in the terminal).
- **Login, not API key** — recommended for students (we run **local Ollama, no API key** — even safer).
- **Vibe-Coding lifecycle:** Idea → **PRD** → **Plan** → **TODO (500–1000 tasks)** → Verify → Execute → Push.
  Three base files: `prd.md`, `plan.md`, `todo.md`.

## Why we're well-positioned
HW6 already gave us: two-agent **FastMCP** orchestration, a **free-NL protocol + decode-to-belief** LLM layer,
a **league/series** runner, a **cross-group MCP bridge** (the bonus, played live), and a professional shared
layer (gatekeeper/config/cost/SDK/CLI/CI/tests, ≤150-line files). ~70% of the substrate transfers.

## Open questions (fill from the full brief; isolated behind config/TBD so changes are cheap)
- Exact **question/answer + guess scoring** (what counts as win/tie/loss for player vs judge).
- The **corpus / article source** (a provided dataset? free choice? Wikipedia/arXiv?).
- **League logistics**: pairing, scheduling, how inter-group MCP connection works (ngrok like the bonus?).
- **Deadline** and submission format.
- Whether the "American format" answers are graded for correctness or only the final guesses.
