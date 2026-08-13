"""Settlement consensus signature (kit §6 CORE) — spaced form, sign-then-insert, byte-exact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pursuit.report.artifacts import build_result_artifact
from pursuit.report.consensus import (
    CONSENSUS_KEY,
    consensus_scope,
    consensus_signature,
    mutual_agreement_scope,
    mutual_agreement_signature,
    settlement,
    sign_consensus,
    verify_consensus,
)

_VECTORS = Path("reference/copthief-league-protocol/vectors/report_consensus.json")


@pytest.mark.skipif(not _VECTORS.exists(), reason="league conformance kit not present")
def test_matches_kit_report_consensus_vectors_byte_exact() -> None:
    data = json.loads(_VECTORS.read_text(encoding="utf-8"))
    for vec in data["vectors"]:
        assert consensus_signature(vec["report"]) == vec["signature"]  # spaced form
        assert sign_consensus(vec["report"]) == vec["signed_report"]  # sign-then-insert
        assert verify_consensus(vec["signed_report"]) is True
        # the compact §2 form must NOT reproduce it (the trap Alon's team found)
        compact = hashlib.sha256(json.dumps(
            vec["report"], sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode()).hexdigest()
        assert compact == vec["compact_form_sha256"] and compact != vec["signature"]


def test_signature_excludes_its_own_key() -> None:
    body = {"game_id": "g", "aggregate": {"winner_group": "a"}}
    signed = sign_consensus(body)
    assert signed[CONSENSUS_KEY] == consensus_signature(body)
    assert verify_consensus(signed)
    signed["aggregate"]["winner_group"] = "b"  # tamper
    assert not verify_consensus(signed)


def test_scope_is_trimmed_to_agreement_only_fields() -> None:
    summary = {"game_id": "nis-yar1-vs-opp", "group_id": "nis-yar1",
               "totals": {"nis-yar1": 20, "opp": 5}, "tie": False, "winner": "nis-yar1",
               "config_sha256": "deadbeef",
               "sub_games": [{"sub_game_number": 1, "roles": {"nis-yar1": "police", "opp": "thief"},
                              "result": "capture", "winner_role": "police", "steps": 12,
                              "game_uid": "u", "audit": {"passed": True, "forgery": False}}]}
    artifact = build_result_artifact(summary, "nis-yar1", "opp")
    scope = consensus_scope(artifact)
    assert set(scope) == {"game_id", "aggregate", "sub_games"}
    assert set(scope["sub_games"][0]) == {"sub_game_number", "roles", "result",
                                          "winner_group", "tie", "score"}
    # the settlement block is no longer embedded in the result (template conformance, §3.17),
    # but the builder still signs + verifies a self-consistent consensus scope on demand.
    assert "settlement" not in artifact
    assert verify_consensus(settlement(artifact))


def test_mutual_agreement_scope_uses_guide_compact_hash() -> None:
    result = {
        "game_id": "anrbj666-vs-nis-yar1",
        "game_uid": "uid-123",
        "sub_games": [{"sub_game_number": 1, "roles": {"nis-yar1": "thief",
                       "anrbj666": "police"}, "result": "capture",
                       "winner_group": "anrbj666", "tie": False,
                       "score": {"nis-yar1": 5, "anrbj666": 20}}],
        "final_result": {"total_score": {"nis-yar1": 5, "anrbj666": 20},
                         "sub_games_won": {"nis-yar1": 0, "anrbj666": 1},
                         "ties": 0, "winner_group": "anrbj666",
                         "series_tie": False},
    }
    scope = mutual_agreement_scope(result)
    assert set(scope) == {"game_id", "game_uid", "sub_games"}
    assert set(scope["sub_games"][0]) == {
        "sub_game_number", "result", "roles", "score", "winner_group"}
    assert mutual_agreement_signature(result) == hashlib.sha256(
        json.dumps(scope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()
