# NotebookLM Questions — paste these, bring back the answers

Two chatbots exist: **[BOOK]** = the rule-book notebook, **[CODE]** = the simulator-code notebook.
Priority order — Q1–Q4 gate implementation decisions, ask them first.

---

**Q1 [BOOK] — hash construction (gates our crypto module):**
"The book's reference commit function puts the nonce INSIDE the canonical JSON
(`SHA256(canonical_json({state, move, intent, nonce}))`), but the reference repo computes
`sha256(canonical_json(payload) + '|' + nonce)`. Which construction is authoritative for league
cross-audits — or is the hash construction itself a term both groups must negotiate and lock
before the series?"

**Q2 [BOOK] — scent formula lock (gates our scent module):**
"Rule 23 requires locking the scent model before each series. If both groups mutually agree to
use the reference repo's subtractive decay and max-merge deposit instead of the book's
multiplicative equation τ(t+1)=max(0,(1−ρ)·τ+Δτ), is that a legal 'upgrade' — or are the book's
emission/decay equations fixed like the Table 16 parameters?"

**Q3 [BOOK] — the two missing captures + 5th barrier option (gates our rules module):**
"Must the cop be able to place a barrier on its own current cell (5 placement options total)?
And are barrier-on-thief capture (rule 46) and jailed-thief capture (rule 47) mandatory in every
league game, even when playing against a peer built on the reference simulator, which implements
neither?"

**Q4 [BOOK] — identical shared engine across the two repos (gates our release plan):**
"May the cop and thief GitHub repos share an identical engine codebase (same package, different
config dirs, different strategy modules and entry roles), or does Zero-Trust require the two
repos to contain independently developed code?"

**Q5 [BOOK] — survival counting:**
"For the thief's survival threshold of 35 valid moves: do STAY/HOLD actions and the cop's barrier
turns count toward the 35, and is survival adjudicated on the thief's own step counter or on a
shared turn count?"

**Q6 [BOOK] — timeout endings:**
"If a peer times out or crashes mid-game, the book mandates technical loss 0/0 — must the
surviving peer still run and email the cryptographic log audit for that sub-game, and what
result string goes in the result JSON?"

**Q7 [BOOK] — step-0 signing key:**
"Rule 24 says the hardware declaration is 'signed cryptographically with a pre-supplied key' —
will a key be distributed by the course staff, or does the reference repo's nonce-based SHA-256
commit-reveal of the spec record satisfy this rule?"

**Q8 [BOOK] — 4-stage protocol strictness:**
"Is the literal 4-stage per-step protocol (Commit → Acknowledge → Reveal → Final Audit) required,
or is the reference repo's compressed flow — per-turn commit with a single end-of-game reveal of
all nonces — compliant?"

**Q9 [BOOK] — forgery scoring + counted-game bookkeeping:**
"(a) When a post-game audit catches tampering, what exact scores go in the result JSON for a
forgery ending, and must both groups still email matching results? (b) Who records which series
against a given opponent is the counted one — must the counted-games-so-far declaration appear
inside the signed declaration JSON or only in the negotiation?"

**Q10 [CODE] — turn-loop internals (implementation aid):**
"Walk through one full turn on the wire: which peer initiates, the exact order of
negotiate/receive_turn calls, what the TurnMessage seal covers, when belief/smell updates are
applied, and where a timeout is detected. Then explain how the series loop swaps roles between
sub-games and how game_uid is derived."

---

## Grade-formula question for the professor directly (WhatsApp/forum, not NotebookLM):
"How do league placement (75–100), the code-quality review, and the computational-fairness bonus
combine into the final project grade? And is the HW6-bonus (+ up to 10) added on top of 100?"
