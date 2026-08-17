"""NajAmjad's fixed Cop--Thief interoperability terms."""

from __future__ import annotations

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex

NAJAMJAD_GROUP_ID = "najamjad"
NAJAMJAD_TERMS: dict[str, object] = {
    "board_size": 7,
    "axis_origin_corner": "top-left",
    "axis_start_index": 0,
    "cop_start": [0, 0],
    "thief_start": [3, 3],
    "max_steps": 35,
    "barriers_max": 14,
    "num_games": 6,
    "smell_grid_size": 5,
    "decay_per_step": 0.1,
    "emit_intensity": 0.9,
    "min_center_intensity": 0.5,
    "hint_max_words": 15,
    "setting": "New York",
}

NAJAMJAD_TERMS_SHA256 = "a284082dfb1572236f1b614d29295a99625539c7d33a096f7f8921bafbc3d08d"
NAJAMJAD_SCENT_MODEL = "subtractive_chebyshev_v1"
NAJAMJAD_SCENT_SHA256 = "81ebee59640e80eae8ca9ee5f86abd26e7edf5cdbb27d15925cb6ee45ca6ddf4"


def terms_sha256() -> str:
    """Return the digest of exactly the fourteen signed terms."""
    return sha256_hex(canonical_bytes(NAJAMJAD_TERMS))


def validate_terms() -> None:
    """Fail fast if a local edit drifts from the opponent's published contract."""
    actual = terms_sha256()
    if actual != NAJAMJAD_TERMS_SHA256:
        raise ValueError(f"NajAmjad terms drifted: expected {NAJAMJAD_TERMS_SHA256}, got {actual}")
