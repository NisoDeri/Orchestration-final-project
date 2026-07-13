"""Crypto seam — canonical hashing, commit dialects, Ed25519 signing (D3/D14).

``make_hash_dialect`` is the single construction point for the commit dialect: the
dialect id comes from the SIGNED shared ``crypto`` config block (rule-23 locked), never
from defaults scattered around the engine. Default ``book`` per NotebookLM ruling A1
(2026-07-13); ``reference`` remains available for stock-reference partners by explicit
negotiation.
"""

from __future__ import annotations

from collections.abc import Mapping

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex
from pursuit.domain.crypto.dialects import (
    BookDialect,
    HashDialect,
    ReferenceDialect,
    generate_nonce,
)
from pursuit.domain.crypto.signing import generate_keypair, sign, verify_signature
from pursuit.exceptions import ConfigError

_DIALECTS: dict[str, type[HashDialect]] = {
    BookDialect.name: BookDialect,
    ReferenceDialect.name: ReferenceDialect,
}

#: NotebookLM ruling A1 — the book construction is authoritative for cross-audits.
DEFAULT_DIALECT = BookDialect.name


def make_hash_dialect(crypto_cfg: Mapping[str, object] | None = None) -> HashDialect:
    """Build the negotiated commit dialect from the signed ``crypto`` config block.

    A missing block or missing ``dialect`` key means ``book`` (ruling A1). Anything
    outside the negotiable set is a ConfigError — fail fast at startup, never
    mid-series (exceptions.py discipline).
    """
    name = (crypto_cfg or {}).get("dialect", DEFAULT_DIALECT)
    if not isinstance(name, str) or name not in _DIALECTS:
        raise ConfigError(
            f"unknown crypto dialect {name!r}; negotiable values: {sorted(_DIALECTS)}"
        )
    return _DIALECTS[name]()


__all__ = [
    "DEFAULT_DIALECT",
    "BookDialect",
    "HashDialect",
    "ReferenceDialect",
    "canonical_bytes",
    "generate_keypair",
    "generate_nonce",
    "make_hash_dialect",
    "sha256_hex",
    "sign",
    "verify_signature",
]
