from kitgame.engine import GameEngine
from kitgame.adapter import seal_turn
from kitgame.model import Action, Player
from kitgame.rules import apply_action, legal_actions
from pursuit.peer.sealing import SealedLog
from kitgame.najamjad_terms import (
    NAJAMJAD_SCENT_MODEL,
    NAJAMJAD_TERMS_SHA256,
    terms_sha256,
    validate_terms,
)


def test_movement_stays_inside_board() -> None:
    engine = GameEngine()
    result = engine.play(Action.STAY)
    assert result.position == (0, 0)
    assert Action.SOUTH not in legal_actions(result.state, Player.SOUTH)


def test_claiming_beacon_scores_once() -> None:
    state = GameEngine().state
    state = state.__class__(positions={Player.NORTH: (3, 3), Player.SOUTH: (6, 6)})
    first = apply_action(state, Player.NORTH, Action.CLAIM)
    second = apply_action(first.state, Player.NORTH, Action.CLAIM)
    assert first.claimed_beacon == (3, 3)
    assert second.claimed_beacon is None
    assert second.state.score(Player.NORTH) == 1


def test_two_claims_finish_game() -> None:
    state = GameEngine().state
    state = state.__class__(positions={Player.NORTH: (3, 3), Player.SOUTH: (6, 6)})
    first = apply_action(state, Player.NORTH, Action.CLAIM)
    second_state = first.state.__class__(
        turn=first.state.turn,
        positions={Player.NORTH: (1, 5), Player.SOUTH: (6, 6)},
        beacons=first.state.beacons,
        claimed=first.state.claimed,
    )
    result = apply_action(second_state, Player.NORTH, Action.CLAIM)
    assert result.finished


def test_adapter_hides_action_and_position_until_audit() -> None:
    log = SealedLog({"dialect": "reference"})
    wire, record = seal_turn(log, Player.NORTH, GameEngine().state, Action.SCAN, 1)
    assert wire["sender"] == "police"
    assert wire["commit"] == record["commit"]
    assert "position" not in wire
    assert "action" not in wire
    assert SealedLog.audit_verify([record], log.dialect)[0]["ok"]


def test_najamjad_terms_are_byte_exact() -> None:
    assert terms_sha256() == NAJAMJAD_TERMS_SHA256
    assert NAJAMJAD_SCENT_MODEL == "subtractive_chebyshev_v1"
    validate_terms()
