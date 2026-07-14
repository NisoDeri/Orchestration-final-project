"""Signed-agreement terms: build, sign, verify (INTEROP §2.1/§3.3/§4; DECISIONS D3).

The wire ``terms`` dict is the COMPLETE signed contract — a stock reference peer
performs an exact-dict-equality check, so extra keys break the handshake (INTEROP §2.1,
§7 landmine 9). Our D3 dialect ids (``crypto.dialect`` / ``pheromones.dialect``)
therefore live in the per-game config + rule-23 lock (``config_sha256``) and are
injected into the wire terms ONLY when both peers agreed to the extended shape via the
shared flag ``negotiation.wire_dialect_terms = true`` in game.json. Flag absent/false =
the stock 14-key reference shape; the dialects still bind out-of-band through the
signed per-game config file.

Pure functions over loaded config trees — zero I/O (architecture.md domain layer).
"""

from __future__ import annotations

from typing import Any

from pursuit.domain.crypto.canonical import canonical_bytes
from pursuit.domain.crypto.dialects import ReferenceDialect
from pursuit.exceptions import ConfigError, NegotiationError
from pursuit.shared.config import ConfigManager

#: Wire term -> shared game.json dotted path. EXACTLY INTEROP §2.1's 14 keys, in the
#: documented order (order is cosmetic — every hash sorts keys; the SET is the contract).
WIRE_TERM_SOURCES: dict[str, str] = {
    "board_size": "board_and_agents.grid_size",
    "smell_grid_size": "pheromones.pheromone_grid_size",
    "decay_per_step": "pheromones.pheromone_decay",
    "emit_intensity": "pheromones.pheromone_center_intensity",
    "min_center_intensity": "pheromones.pheromone_min_center_intensity",
    "max_steps": "movement_and_barriers.max_moves",
    "barriers_max": "movement_and_barriers.max_barriers",
    "setting": "world.map_area",
    "hint_max_words": "world.hint_max_words",
    "axis_origin_corner": "board_and_agents.axis_origin_corner",
    "axis_start_index": "board_and_agents.axis_start_index",
    "thief_start": "board_and_agents.thief_start",
    "cop_start": "board_and_agents.cop_start",
    "num_games": "network_and_league.num_games",
}

#: D3 dialect ids -> config paths; injected only under ``negotiation.wire_dialect_terms``.
DIALECT_TERM_SOURCES: dict[str, str] = {
    "crypto_dialect": "crypto.dialect",
    "scent_dialect": "pheromones.dialect",
}

#: Shared game.json flag gating the extended (dialects-on-the-wire) terms shape.
WIRE_DIALECT_FLAG = "negotiation.wire_dialect_terms"


def _wire_dialect_terms_enabled(config: ConfigManager) -> bool:
    """Read the shared extended-shape flag; absent means False (stock 14-key shape)."""
    try:
        flag = config.game(WIRE_DIALECT_FLAG)
    except ConfigError:
        return False
    if not isinstance(flag, bool):
        raise ConfigError(f"'{WIRE_DIALECT_FLAG}' must be a JSON boolean, got {flag!r}")
    return flag


def build_terms(config: ConfigManager) -> dict[str, Any]:
    """Assemble the signed wire ``terms`` dict from the SHARED game.json.

    Returns the exact 14 INTEROP §2.1 keys — plus the two D3 dialect keys iff the
    shared ``negotiation.wire_dialect_terms`` flag is true (see module docstring for
    the stock-reference landmine this resolves). Any missing source term raises
    ConfigError (fail-fast BEFORE the handshake, never mid-series).
    """
    terms: dict[str, Any] = {key: config.game(path) for key, path in WIRE_TERM_SOURCES.items()}
    if _wire_dialect_terms_enabled(config):
        for key, path in DIALECT_TERM_SOURCES.items():
            terms[key] = config.game(path)
    return terms


def agreement_signature(terms: dict[str, Any], nonce: str) -> str:
    """Agreement signature: ``sha256(canonical_json(terms) + "|" + nonce)``.

    Per INTEROP §3.3 (and the §3.4 hasher table) this is ALWAYS the dialect-A
    pipe-append construction — the reference's ``CommitReveal.commit_of`` — even when
    the per-step commit dialect negotiated for the series is ``book``: it is what an
    unmodified reference peer verifies. Golden vector: the INTEROP §2.1 worked terms
    + nonce reproduce ``167fef4e...7472d``.
    """
    return ReferenceDialect().commit(terms, nonce)


def verify_agreement_signature(terms: dict[str, Any], nonce: str, signature: str) -> bool:
    """Constant-time check of an opponent's agreement signature (INTEROP §4 step 3b)."""
    return ReferenceDialect().verify(terms, nonce, signature)


def verify_terms(mine: dict[str, Any], theirs: dict[str, Any]) -> None:
    """Exact-dict-equality gate (INTEROP §4 step 3a) — NegotiationError on divergence.

    Equality is judged per key on the canonical WIRE bytes, so types matter exactly as
    they do on the wire (``0.1`` float vs ``"0.1"`` string, ``35`` int vs ``35.0``
    float, ``true`` bool vs ``1`` int all mismatch — §7 landmine 9). The error names
    the FIRST diverging key in sorted-key order (deterministic on both peers). There
    is no in-protocol bargaining: terms are agreed out-of-band and typed identically.
    """
    if not isinstance(theirs, dict):
        raise NegotiationError(f"opponent terms is not a dict: {type(theirs).__name__}")
    for key in sorted(set(mine) | set(theirs)):
        if key not in theirs:
            raise NegotiationError(f"terms mismatch at '{key}': missing from opponent terms")
        if key not in mine:
            raise NegotiationError(f"terms mismatch at '{key}': unagreed extra term from opponent")
        if not _same_wire_value(mine[key], theirs[key]):
            raise NegotiationError(
                f"terms mismatch at '{key}': ours={mine[key]!r} theirs={theirs[key]!r}"
            )


def _same_wire_value(a: Any, b: Any) -> bool:
    """Byte-exact equality under the compact canonical JSON (the wire's own semantics)."""
    try:
        return canonical_bytes(a) == canonical_bytes(b)
    except TypeError:  # non-JSON value cannot have come off the wire — never equal
        return False
