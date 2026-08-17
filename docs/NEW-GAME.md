# New Cop--Thief implementation

This branch starts a new Cop--Thief implementation without modifying the
existing `pursuit` implementation.

The authoritative match contract is NajAmjad's published terms. The signed
terms are fixed at a 7x7 board, cop `[0, 0]`, thief `[3, 3]`, 35 steps, 14
barriers, six sub-games, and the reference pipe-appended commit construction.

## Kit reuse

The new game is deliberately split into two layers:

- `src/kitgame/najamjad_terms.py` contains the exact fourteen-term contract and
  a fail-fast digest check.
- The existing `pursuit` packages remain the integration layer for MCP transport,
  handshake, canonical JSON, commit–reveal, audit, reports, and self-play.

Every game-specific action must be included in the sealed payload before it is
committed. The payload must be serialized with the kit's canonical JSON helper;
no game code may call `json.dumps` directly for a hashed value.

## Current status

The deterministic game core and a signed configuration profile are in place.
The local profile records the `nis-yar1` identity, both role repositories,
their current local HEAD commits, and the configured cop/thief endpoints.
Re-check the commits after every push; rule 53 requires the declaration to
match the code that actually plays.
The next integration step is the new two-process Cop and Thief runtime, followed
by a local six-game self-play runner and endpoint retargeting at each sub-game.

## Strategy modes

Friendly runs use `friendly_dummy` automatically when `game.mode = "friendly"`.
The dummy brain ignores belief and opponent hints, varies legal actions using
the injected per-game random generator, and emits generic text. Opponent
profiling is disabled for friendly runs.

Counted runs use the configured serious police/thief brains when
`game.mode = "counted"`. The mode must be selected explicitly with the CLI;
never change a friendly run into a counted run accidentally.
