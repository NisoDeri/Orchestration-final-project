# PRD-6 — Security + Crypto: Commit-Reveal, Audit, Step-0 (Book Ch5; roadmap stage 6)

## Purpose
Wrap the proven remote comms in the **Commit-Reveal protocol** — the referee replacement
(brief §7, §14.6). Kills the three cheats: time-travel, change-after-seeing, denial. Crypto sits
on top of comms already proven reliable so a failure is never ambiguous between "network" and
"crypto". This stage earns the **Integrity grade**.

## In scope
- Per-step sealing + commit, end-of-game mutual audit, tamper forfeit.
- **Both hash dialects (D3) — mandatory in this PRD.**
- Nonce discipline, Step-0 signed hardware declaration with `github_commit`.
- Scent-formula lock exchange (rule 23) as a sealed pre-series record (formula from PRD-4).
- Verification core reused later by the PRD-7 replay app.

## Out of scope
Replay UI (PRD-7), Gmail (PRD-7), asymmetric keys unless the lecturer supplies one (see Risks).

## Functional requirements
- **FR-6.1 Dual-dialect commit hash (D3).** Config-selected, locked pre-series, both fully
  implemented and golden-tested:
  - `reference` (default): `sha256(canonical_json(payload) + "|" + nonce)` — canonical JSON =
    `sort_keys=True, ensure_ascii=False, separators=(",",":")`; nonce pipe-appended OUTSIDE the
    JSON (reference_map §2.3, landmine #1).
  - `book`: `sha256(canonical_json({...payload, "nonce": nonce}))` — nonce a key INSIDE the JSON,
    per the brief §7 reference snippet.
  The two are incompatible; the active dialect is a negotiated term so a literal-book partner
  never fails our audit.
- **FR-6.2 Sealed step record.** Every turn seals the reference-schema payload — step, canonical
  state string, position, move, `intent` (truth/lie) + duplicate `verdict`, hint,
  prompt_discussion (LLM prompt/reasoning/bluff class), model, tokens_step/total,
  response_seconds, random_move (reference_map §2.3) — and sends only `H_commit` in the
  TurnMessage (rule 17; brief §7 stage 1 Commit).
- **FR-6.3 Nonce discipline.** Fresh `secrets.token_hex(16)` per commitment; **secret until the
  final audit** (rule 18); `secrets.compare_digest` for our own verification comparisons
  (brief §7), while emitting reference-compatible records.
- **FR-6.4 Protocol staging.** Reference wire = 2-stage (commit rides the TurnMessage; all
  nonces revealed once in the end-game AuditPayload). We ship this as the interop default and
  document the mapping to the book's 4 stages (Commit→Acknowledge→Reveal→Final Audit): Ack ≙
  opponent's next turn message locking the token; Reveal ≙ the move/hint fields sent alongside
  the commit; Final Audit ≙ AuditPayload exchange. Per-step Ack/Reveal as a negotiable upgrade
  if a partner requires literal 4-stage (book p.34: contract is a floor).
- **FR-6.5 Mutual audit + iron law.** At game end exchange AuditPayloads (best-effort both ways);
  re-hash every opponent record against its committed digest; **any mismatch ⇒ result rewritten
  to tamper forfeit, cheater scores 0** regardless of board result (rules 19, 21–22). Unlike the
  reference (gap: audit skipped on timeout/stopped), we run/attempt the audit on ALL endings
  incl. timeout (D4).
- **FR-6.6 Truthful-claim enforcement.** Cop's `capture_claim` on every MOVE; thief's
  crypto-obligated honest `claim_response` (rule 21); barrier declarations audited against
  sealed moves (rules 14–15, 46).
- **FR-6.7 Step-0 signed hardware declaration.** records[0] of the same commit chain:
  OS, CPU cores/freq, RAM, GPU/VRAM, LLM model, code version, group name, sub-game number, and
  the **real `github_commit`** (`git rev-parse HEAD`, refreshed per game) — never the reference's
  literal `"unknown"` (rules 24, 53; reference gaps #13–14). Token budget locked alongside.
- **FR-6.8 Rule-23 scent lock record.** The PRD-4 formula+numeric-example hash exchanged and
  sealed pre-series; deviation detected at audit voids the game (rule 23).
- **FR-6.9 Verification core.** `audit_records(records) -> {passed, verified_steps,
  failed_steps}` as a pure, dialect-aware function — the single verifier used by the live audit,
  the replay app (PRD-7), and tests (rule 20 groundwork).

## Acceptance criteria (testable)
1. **Runs end-to-end:** full series over the PRD-5 tunnel with commit-reveal active; both sides'
   audits pass; logs contain the complete verified chain incl. Step-0.
2. Dialect golden tests: fixed payload+nonce reproduce known digests in BOTH dialects; dialect
   selected purely by config; cross-dialect verification fails loudly (proving incompatibility).
3. Tamper test: mutate one revealed field (move, hint, intent, state, nonce) in a recorded game
   ⇒ audit fails on exactly that step ⇒ result rewritten to tamper forfeit 0 for the cheater.
4. Replay-attack test: re-sent old TurnMessage is deduped, never re-committed.
5. Step-0 test: declaration present as records[0], `github_commit` matches `git rev-parse HEAD`
   of the running tree; changes between sub-games are reflected.
6. Timeout-audit test: forced timeout still produces an exchanged (or best-effort recorded)
   audit and 0/0 scoring (D4).
7. Gates: ≤150 lines/file, ruff, coverage ≥85%; `secrets` used everywhere (no `random` for
   nonces).

## Dependencies
PRD-2 (wire + AuditPayload envelope), PRD-4 (hint/intent/token fields to seal), PRD-5 (proven
remote comms underneath).

## Risks
- Partner uses a third hash construction → dialect is a pinned pre-series negotiation item (D13
  checklist #1); our golden-test fixtures double as the negotiation worked example.
- "Pre-supplied key" (brief §7 Step-0) turns out to be a real asymmetric keypair from the
  lecturer → sealing module keeps a signing seam; ed25519 add-on estimated small (reference has
  none either, reference_map gap #13). Clarify via NotebookLM/forum before W3 ends.
- Duplicate `intent`/`verdict` fields dropped by refactoring → hashes break vs partners;
  golden fixtures pin the exact payload schema.
