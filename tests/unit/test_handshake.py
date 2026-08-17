"""Unit tests for pursuit.peer.handshake — two in-memory peers, no sockets, no sleeps."""

import json
import queue
from pathlib import Path
from types import SimpleNamespace

import pytest

from pursuit.domain.crypto import generate_keypair
from pursuit.domain.game_ids import derive_game_ids
from pursuit.exceptions import CryptoError, DeadlineError, NegotiationError, TransportError
from pursuit.peer.agreement import build_agreement_message, build_identity
from pursuit.peer.handshake import Handshake, run_handshake
from pursuit.shared.config import ConfigManager

ROOT = Path(__file__).resolve().parents[2]


class FakeClock:
    """Deterministic time: sleep() advances the clock, nothing actually waits."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class QueueTransport:
    """In-memory wire: negotiate() JSON-round-trips into the opponent's inbox."""

    def __init__(self, opponent_inboxes) -> None:
        self._inboxes = opponent_inboxes
        self.sent: list[dict] = []

    def negotiate(self, message: dict) -> None:
        wire = json.loads(json.dumps(message, ensure_ascii=False))  # simulate the wire
        self.sent.append(wire)
        self._inboxes.agreements.put(wire)


class FlakyTransport(QueueTransport):
    """Fails the first ``failures`` sends — exercises the retry loop."""

    def __init__(self, opponent_inboxes, failures: int) -> None:
        super().__init__(opponent_inboxes)
        self.failures = failures
        self.attempts = 0

    def negotiate(self, message: dict) -> None:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise TransportError("server not up yet")
        super().negotiate(message)


class DelayedAgreementTransport(QueueTransport):
    """Opponent only answers after seeing repeated offers for the same window."""

    def __init__(self, opponent_inboxes, own_inboxes, reply: dict, after: int) -> None:
        super().__init__(opponent_inboxes)
        self._own_inboxes = own_inboxes
        self._reply = reply
        self._after = after
        self.offers = 0

    def negotiate(self, message: dict) -> None:
        self.offers += 1
        super().negotiate(message)
        if self.offers == self._after:
            self._own_inboxes.agreements.put(
                json.loads(json.dumps(self._reply, ensure_ascii=False))
            )


def make_config(
    group_id: str,
    mutate_game=None,
    counted: int | None = 3,
    label: str | None = None,
) -> ConfigManager:
    game = json.loads((ROOT / "config" / "police" / "game.json").read_text(encoding="utf-8"))
    if mutate_game is not None:
        mutate_game(game)
    game_block = {
        "group_id": group_id,
        "group_name": group_id.title(),
        "members": ["A Member", "B Member"],
        "repos": {"cop": f"https://github.com/{group_id}/cop",
                  "thief": f"https://github.com/{group_id}/thief"},
        "mcp_servers": {"cop": "http://127.0.0.1:8802/mcp",
                        "thief": "http://127.0.0.1:8801/mcp"},
    }
    if counted is not None:
        game_block["counted_games_so_far"] = counted
    if label is not None:
        game_block["label"] = label
    private = {
        "game": game_block,
        "trash_talk": {"model": "stub"},
        "network": {"connect_timeout_seconds": 60, "retry_interval_seconds": 1.0,
                    "poll_interval_seconds": 0.5},
    }
    return ConfigManager(game_terms=game, private_terms=private, rate_limits={})


def make_inboxes():
    return SimpleNamespace(agreements=queue.Queue())


@pytest.fixture(scope="module")
def keypairs():
    return generate_keypair(), generate_keypair()


def handshake_both(cfg_a, cfg_b, keypairs) -> tuple[Handshake, Handshake]:
    """Run the symmetric flow for both peers with in-memory queues."""
    kp_a, kp_b = keypairs
    inboxes_a, inboxes_b = make_inboxes(), make_inboxes()
    transport_a, transport_b = QueueTransport(inboxes_b), QueueTransport(inboxes_a)
    clock = FakeClock()
    # Seed A's inbox with B's agreement (peers send concurrently in real play).
    transport_b.negotiate(build_agreement_message(cfg_b, kp_b[1]))
    result_a = run_handshake(transport_a, inboxes_a, cfg_a, kp_a,
                             clock=clock, sleep=clock.sleep)
    # A's send above landed in B's inbox — B can now complete its own side.
    result_b = run_handshake(transport_b, inboxes_b, cfg_b, kp_b,
                             clock=clock, sleep=clock.sleep)
    return result_a, result_b


class TestAgreementMessage:
    def test_message_shape_and_self_verifying_signature(self, keypairs):
        from pursuit.domain.negotiation import verify_agreement_signature

        config = make_config("aa-team")
        message = build_agreement_message(config, keypairs[0][1])
        assert {"terms", "nonce", "signature", "identity"}.issubset(message)
        assert message["config_sha256"] == config.config_sha256()
        assert message["scent_model_sha256"] == (
            "81ebee59640e80eae8ca9ee5f86abd26e7edf5cdbb27d15925cb6ee45ca6ddf4"
        )
        assert message["wire_shape_sha256"] == (
            "229ae6487a418c3fcb6da9be404de2f2533c288ebc228811bff6dedc4164d6f7"
        )
        assert message["commit_order"] == "thief_first"
        assert message["turn_order"] == "cop_first"
        assert len(message["nonce"]) == 32 and int(message["nonce"], 16) >= 0
        assert verify_agreement_signature(
            message["terms"], message["nonce"], message["signature"])

    def test_identity_block_carries_d14_extensions(self, keypairs):
        identity = build_identity(make_config("aa-team"), keypairs[0][1])
        assert identity["group_id"] == "aa-team"
        assert identity["counted_games_so_far"] == 3  # rule 37 / A9b ledger
        assert identity["ed25519_public_key"].startswith("-----BEGIN PUBLIC KEY-----")
        assert "spec" not in identity  # step0 owns hardware collection

    def test_counted_games_defaults_to_zero_for_fresh_ledger(self, keypairs):
        identity = build_identity(make_config("aa-team", counted=None), keypairs[0][1])
        assert identity["counted_games_so_far"] == 0

    def test_runtime_scent_override_changes_declared_lock(self, keypairs):
        cfg = make_config("aa-team")
        cfg.override_game("pheromones.dialect", "multiplicative_book_v1")
        message = build_agreement_message(cfg, keypairs[0][1])
        assert message["scent_model_sha256"] == (
            "934c220d5bf62acaa3297c6c9d723ea954c220260b02292ca17f6d5daef9f4d9"
        )

    def test_labelled_series_declares_both_kit_aliases(self, keypairs):
        message = build_agreement_message(
            make_config("aa-team", label="counted-1"), keypairs[0][1]
        )
        assert message["game_label"] == message["label"] == "counted-1"


class TestSuccessfulHandshake:
    def test_ids_identical_on_both_sides(self, keypairs):
        result_a, result_b = handshake_both(make_config("aa-team"), make_config("zz-team"),
                                            keypairs)
        assert result_a.game_id == result_b.game_id == "aa-team-vs-zz-team"
        assert result_a.game_uid == result_b.game_uid
        assert len(result_a.game_uid) == 36

    def test_labelled_ids_identical_on_both_sides(self, keypairs):
        result_a, result_b = handshake_both(
            make_config("aa-team", label="counted-1"),
            make_config("zz-team", label="counted-1"),
            keypairs,
        )
        expected = derive_game_ids(
            result_a.terms, ["aa-team", "zz-team"], label="counted-1"
        )
        assert (result_a.game_id, result_a.game_uid) == expected
        assert (result_b.game_id, result_b.game_uid) == expected

    def test_terms_agreed_and_equal(self, keypairs):
        result_a, result_b = handshake_both(make_config("aa-team"), make_config("zz-team"),
                                            keypairs)
        assert result_a.terms == result_b.terms
        assert result_a.terms["board_size"] == 7

    def test_pubkeys_exchanged_crosswise(self, keypairs):
        kp_a, kp_b = keypairs
        result_a, result_b = handshake_both(make_config("aa-team"), make_config("zz-team"),
                                            keypairs)
        assert result_a.opponent_pubkey == kp_b[1].decode("ascii")
        assert result_b.opponent_pubkey == kp_a[1].decode("ascii")
        assert "PUBLIC KEY" in result_a.opponent_pubkey

    def test_opponent_identity_and_counted_games(self, keypairs):
        result_a, result_b = handshake_both(make_config("aa-team"), make_config("zz-team"),
                                            keypairs)
        assert result_a.opponent_identity["group_id"] == "zz-team"
        assert result_b.opponent_identity["group_id"] == "aa-team"
        assert result_a.opponent_counted_games == 3  # rule 37 / A9b ledger exchange

    def test_send_retries_until_opponent_server_up(self, keypairs):
        kp_a, kp_b = keypairs
        inboxes_a, inboxes_b = make_inboxes(), make_inboxes()
        transport_a = FlakyTransport(inboxes_b, failures=3)
        clock = FakeClock()
        QueueTransport(inboxes_a).negotiate(
            build_agreement_message(make_config("zz-team"), kp_b[1]))
        result = run_handshake(transport_a, inboxes_a, make_config("aa-team"), kp_a,
                               clock=clock, sleep=clock.sleep)
        assert transport_a.attempts == 4
        assert result.game_id == "aa-team-vs-zz-team"

    def test_reoffers_agreement_while_waiting_for_counterpart(self, keypairs):
        kp_a, kp_b = keypairs
        inboxes_a, inboxes_b = make_inboxes(), make_inboxes()
        reply = build_agreement_message(
            make_config("zz-team"), kp_b[1], sub_game_number=5, role="police"
        )
        transport_a = DelayedAgreementTransport(inboxes_b, inboxes_a, reply, after=3)
        clock = FakeClock()
        result = run_handshake(
            transport_a, inboxes_a, make_config("aa-team"), kp_a,
            clock=clock, sleep=clock.sleep, sub_game_number=5, role="thief"
        )
        assert result.game_id == "aa-team-vs-zz-team"
        assert transport_a.offers == 3


class TestRefusals:
    def _seed_and_run(self, keypairs, message):
        kp_a, _kp_b = keypairs
        inboxes_a = make_inboxes()
        inboxes_a.agreements.put(message)
        return run_handshake(QueueTransport(make_inboxes()), inboxes_a,
                             make_config("aa-team"), kp_a,
                             clock=(clock := FakeClock()), sleep=clock.sleep)

    def test_terms_mismatch_is_dropped_until_deadline(self, keypairs):
        def bigger_board(game):
            game["board_and_agents"]["grid_size"] = 9

        message = build_agreement_message(make_config("zz-team", bigger_board), keypairs[1][1])
        with pytest.raises(DeadlineError, match="never sent"):
            self._seed_and_run(keypairs, message)

    def test_signature_tamper_is_dropped_until_deadline(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        message["signature"] = "0" * 64
        with pytest.raises(DeadlineError, match="never sent"):
            self._seed_and_run(keypairs, message)

    def test_nonce_tamper_is_dropped_until_deadline(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        message["nonce"] = "f" * 32
        with pytest.raises(DeadlineError, match="never sent"):
            self._seed_and_run(keypairs, message)

    def test_missing_group_id_is_dropped_until_deadline(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        del message["identity"]["group_id"]
        del message["group_id"]
        with pytest.raises(DeadlineError, match="never sent"):
            self._seed_and_run(keypairs, message)

    def test_lock_mismatch_is_dropped_until_deadline(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        message["scent_model_sha256"] = "0" * 64
        with pytest.raises(DeadlineError, match="never sent"):
            self._seed_and_run(keypairs, message)

    def test_label_mismatch_is_dropped_until_deadline(self, keypairs):
        message = build_agreement_message(
            make_config("zz-team", label="counted-2"), keypairs[1][1]
        )
        kp_a, _ = keypairs
        inboxes = make_inboxes()
        inboxes.agreements.put(message)
        clock = FakeClock()
        with pytest.raises(DeadlineError, match="never sent"):
            run_handshake(
                QueueTransport(make_inboxes()), inboxes,
                make_config("aa-team", label="counted-1"), kp_a,
                clock=clock, sleep=clock.sleep,
            )

    def test_config_hash_mismatch_is_advisory(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        message["config_sha256"] = "0" * 64
        assert self._seed_and_run(keypairs, message).game_id == "aa-team-vs-zz-team"

    def test_bad_agreement_does_not_prevent_later_valid_agreement(self, keypairs):
        kp_a, kp_b = keypairs
        inboxes_a = make_inboxes()
        inboxes_a.agreements.put({"probe": "hello"})
        inboxes_a.agreements.put(build_agreement_message(make_config("zz-team"), kp_b[1]))
        clock = FakeClock()
        result = run_handshake(
            QueueTransport(make_inboxes()), inboxes_a, make_config("aa-team"), kp_a,
            clock=clock, sleep=clock.sleep
        )
        assert result.game_id == "aa-team-vs-zz-team"

    def test_lock_omission_still_plays(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        del message["scent_model_sha256"]
        assert self._seed_and_run(keypairs, message).game_id == "aa-team-vs-zz-team"

    def test_kit_top_level_identity_shape_plays(self, keypairs):
        message = build_agreement_message(make_config("zz-team"), keypairs[1][1])
        identity = message.pop("identity")
        message["group_id"] = identity["group_id"]
        message["counted_games_played"] = 4
        result = self._seed_and_run(keypairs, message)
        assert result.game_id == "aa-team-vs-zz-team"
        assert result.opponent_counted_games == 4

    def test_empty_inbox_deadline(self, keypairs):
        kp_a, _ = keypairs
        clock = FakeClock()
        with pytest.raises(DeadlineError, match="never sent"):
            run_handshake(QueueTransport(make_inboxes()), make_inboxes(),
                          make_config("aa-team"), kp_a, clock=clock, sleep=clock.sleep)
        assert clock.now >= 60  # polled the full negotiated window, no real sleeping

    def test_unreachable_opponent_deadline(self, keypairs):
        kp_a, _ = keypairs
        clock = FakeClock()
        transport = FlakyTransport(make_inboxes(), failures=10**6)
        with pytest.raises(TransportError, match="unreachable"):
            run_handshake(transport, make_inboxes(), make_config("aa-team"), kp_a,
                          clock=clock, sleep=clock.sleep)
        assert transport.attempts > 1
