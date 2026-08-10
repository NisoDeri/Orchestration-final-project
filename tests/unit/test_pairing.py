"""§7.2 pairing declaration — the refusal truth table (vectors/pairing_declaration.json).

Both league opponents ride ``sub_game_number`` + ``role`` TOP-LEVEL beside the signed
``terms`` (never inside — that would break the signature). The handshake is the only place a
mispairing can be caught: identical terms mint identical ``game_uid``s, so by artifact time a
two-teams-different-series desync is already invisible. These cases pin: (a) sub-game numbers
differ -> refuse; (b) same role -> refuse; (c) same game + complementary roles -> play; and
(d) omission/mistyping on EITHER side -> play (a stock reference peer declares nothing).
"""

import json
import queue
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_handshake import FakeClock, QueueTransport, keypairs, make_config

from pursuit.exceptions import DeadlineError
from pursuit.peer.agreement import build_agreement_message
from pursuit.peer.handshake import run_handshake

__all__ = ["keypairs"]  # re-export the module-scoped fixture for this file

ROOT = Path(__file__).resolve().parents[2]


def _wire(message: dict) -> dict:
    """Round-trip through JSON exactly as QueueTransport does, so ints/strings match the wire."""
    return json.loads(json.dumps(message, ensure_ascii=False))


def _run_against(kp_a, kp_b, *, mine: dict, theirs: dict):
    """Seed A's inbox with B's greeting carrying ``theirs`` RAW top-level (a string stays a
    string on the wire — build_agreement_message would coerce, so we splice it in directly),
    then run A's handshake declaring ``mine``. Terms match both sides; only pairing can refuse."""
    inboxes_a = SimpleNamespace(agreements=queue.Queue())
    greeting = build_agreement_message(make_config("zz-team"), kp_b[1])
    greeting.update(theirs)  # exact opponent wire bytes, outside the signed terms
    inboxes_a.agreements.put(_wire(greeting))
    clock = FakeClock()
    return run_handshake(
        QueueTransport(SimpleNamespace(agreements=queue.Queue())), inboxes_a,
        make_config("aa-team"), kp_a, clock=clock, sleep=clock.sleep, **mine)


PLAY_ROWS = [
    pytest.param({"sub_game_number": 3, "role": "thief"},
                 {"sub_game_number": 3, "role": "police"}, id="same-game-complementary"),
    pytest.param({"sub_game_number": 3, "role": "thief"}, {}, id="opponent-declares-nothing"),
    pytest.param({}, {"sub_game_number": 3, "role": "police"}, id="we-declare-nothing"),
    pytest.param({"sub_game_number": 3, "role": "thief"},
                 {"sub_game_number": "3", "role": "police"}, id="their-number-is-a-string"),
    pytest.param({"sub_game_number": 3, "role": "thief"},
                 {"sub_game_number": 3}, id="partial-role-omitted"),
]


class TestPairingTruthTable:
    @pytest.mark.parametrize("mine,theirs", PLAY_ROWS)
    def test_play_rows(self, keypairs, mine, theirs):
        kp_a, kp_b = keypairs
        result = _run_against(kp_a, kp_b, mine=mine, theirs=theirs)
        assert result.game_id == "aa-team-vs-zz-team"  # got a Handshake, i.e. it played

    def test_sub_game_mismatch_is_dropped_until_deadline(self, keypairs):
        kp_a, kp_b = keypairs
        with pytest.raises(DeadlineError, match="never sent"):
            _run_against(kp_a, kp_b, mine={"sub_game_number": 3, "role": "thief"},
                         theirs={"sub_game_number": 5, "role": "police"})

    def test_stale_lower_sub_game_is_ignored_until_current_arrives(self, keypairs):
        kp_a, kp_b = keypairs
        inboxes_a = SimpleNamespace(agreements=queue.Queue())
        for number in (3, 5):
            greeting = build_agreement_message(make_config("zz-team"), kp_b[1],
                                               sub_game_number=number, role="police")
            inboxes_a.agreements.put(_wire(greeting))
        clock = FakeClock()
        result = run_handshake(
            QueueTransport(SimpleNamespace(agreements=queue.Queue())), inboxes_a,
            make_config("aa-team"), kp_a, clock=clock, sleep=clock.sleep,
            sub_game_number=5, role="thief")
        assert result.game_id == "aa-team-vs-zz-team"

    def test_same_role_is_dropped_until_deadline(self, keypairs):
        kp_a, kp_b = keypairs
        with pytest.raises(DeadlineError, match="never sent"):
            _run_against(kp_a, kp_b, mine={"sub_game_number": 3, "role": "police"},
                         theirs={"sub_game_number": 3, "role": "police"})

    def test_omission_plays_even_when_roles_would_collide(self, keypairs):
        """Omission is never a refusal: our silence disarms the role guard the peer would trip."""
        kp_a, kp_b = keypairs
        result = _run_against(kp_a, kp_b, mine={"sub_game_number": 3},
                              theirs={"sub_game_number": 3, "role": "thief"})
        assert result.game_id == "aa-team-vs-zz-team"


class TestPairingRidesTopLevel:
    def test_fields_are_top_level_outside_terms(self, keypairs):
        message = build_agreement_message(
            make_config("aa-team"), keypairs[0][1], sub_game_number=4, role="thief")
        assert message["sub_game_number"] == 4 and message["role"] == "thief"
        assert "sub_game_number" not in message["terms"] and "role" not in message["terms"]

    def test_omitted_fields_are_absent(self, keypairs):
        message = build_agreement_message(make_config("aa-team"), keypairs[0][1])
        assert "sub_game_number" not in message and "role" not in message


def test_vector_rows_match_our_decisions(keypairs):
    """Drive every row of the shipped vector through the real handshake, decision-for-decision."""
    kp_a, kp_b = keypairs
    vector = json.loads((ROOT / "reference" / "copthief-league-protocol" / "vectors"
                         / "pairing_declaration.json").read_text(encoding="utf-8"))
    for row in vector["refusal_rule"]:
        expected = row["decision"]
        if expected == "play":
            assert _run_against(kp_a, kp_b, mine=row["ours"], theirs=row["theirs"])
        else:
            with pytest.raises(DeadlineError):
                _run_against(kp_a, kp_b, mine=row["ours"], theirs=row["theirs"])
