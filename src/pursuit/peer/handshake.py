"""Symmetric no-initiator handshake (INTEROP §4) — the game clock starts here.

Both peers concurrently SEND their signed agreement (built by peer/agreement.py) retrying
until ``network.connect_timeout_seconds``, RECEIVE the opponent's under the same deadline,
VERIFY terms exact-equality, the agreement signature, then the §7.2 pairing declaration
(refusal, never bargaining), and DERIVE ``game_id``/``game_uid`` independently. D14/rule-37
payloads ride in the unsigned identity block; clock/transport are injected for in-memory tests.
"""

from __future__ import annotations

import queue
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pursuit.domain.game_ids import derive_game_ids
from pursuit.domain.negotiation import verify_agreement_signature, verify_terms
from pursuit.exceptions import CryptoError, DeadlineError, NegotiationError, TransportError
from pursuit.peer.agreement import build_agreement_message
from pursuit.shared.config import ConfigManager


class Transport(Protocol):
    """Outbound wire seam: one ``negotiate`` push (may raise TransportError)."""

    def negotiate(self, message: dict[str, Any]) -> None: ...


class Inboxes(Protocol):
    """Local inbound queues; ``agreements`` is queue-like (``get_nowait``/``Empty``)."""

    agreements: Any


@dataclass(frozen=True)
class Handshake:
    """Everything the runtime needs once both peers agreed (INTEROP §4 step 4)."""

    game_id: str
    game_uid: str
    terms: dict[str, Any]
    opponent_identity: dict[str, Any]
    opponent_pubkey: str | None  # PEM text off the wire (D14); None if peer omitted it
    opponent_counted_games: int | None  # rule-37 ledger count; None if peer omitted it


def _send_with_retry(
    transport: Transport, message: dict, deadline: float, retry: float, clock, sleep
) -> None:
    while True:
        try:
            transport.negotiate(message)
            return
        except TransportError as exc:
            if clock() >= deadline:
                raise TransportError(f"opponent MCP server unreachable: {exc}") from exc
            sleep(retry)


def _is_int(value: Any) -> bool:
    """A comparable sub-game index is a plain int; a bool or ``"3"`` is silence, not a value."""
    return isinstance(value, int) and not isinstance(value, bool)


def _assert_pairing(my_num: Any, my_role: Any, theirs: dict[str, Any]) -> None:
    """§7.2 pairing guard — refuse ONLY on a two-sided contradiction, never on silence.

    Both declare comparable ``sub_game_number`` that DIFFER -> refuse; both declare the same
    ``role`` (same side) -> refuse; otherwise (complementary, or EITHER side omits/mistypes a
    field) -> play. A stock reference peer declares nothing, so silence must always play.
    """
    their_num = theirs.get("sub_game_number")
    if _is_int(my_num) and _is_int(their_num) and my_num != their_num:
        raise NegotiationError(
            f"pairing refused: sub_game_number ours={my_num} theirs={their_num} (§7.2)")
    their_role = theirs.get("role")
    if isinstance(my_role, str) and isinstance(their_role, str) and my_role == their_role:
        raise NegotiationError(f"pairing refused: both declared role={my_role!r} (§7.2)")


def _receive_agreement(inboxes: Inboxes, deadline: float, poll: float, clock, sleep) -> dict:
    while True:
        try:
            message = inboxes.agreements.get_nowait()
        except queue.Empty:
            if clock() >= deadline:
                raise DeadlineError("opponent never sent its agreement") from None
            sleep(poll)
            continue
        if not isinstance(message, dict):
            raise CryptoError(f"malformed agreement message: {type(message).__name__}")
        return message


def run_handshake(
    transport: Transport,
    inboxes: Inboxes,
    config: ConfigManager,
    keypair: tuple[bytes, bytes],
    *,
    sub_game_number: int | None = None,
    role: str | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Handshake:
    """Full symmetric handshake; returns the agreed :class:`Handshake` or refuses.

    Refusal matrix (INTEROP §4): terms mismatch or §7.2 pairing contradiction ->
    NegotiationError; bad signature -> CryptoError; nothing delivered/received before
    ``network.connect_timeout_seconds`` -> Transport/Deadline error. Duplicate deliveries
    are tolerated (retries may leave copies in the queue; the first message wins).
    """
    _private_pem, public_pem = keypair
    mine = build_agreement_message(config, public_pem, sub_game_number=sub_game_number, role=role)
    retry = float(config.private("network.retry_interval_seconds"))
    poll = float(config.private("network.poll_interval_seconds"))
    deadline = clock() + float(config.private("network.connect_timeout_seconds"))

    _send_with_retry(transport, mine, deadline, retry, clock, sleep)
    theirs = _receive_agreement(inboxes, deadline, poll, clock, sleep)

    their_terms, their_nonce = theirs.get("terms"), theirs.get("nonce")
    their_signature = theirs.get("signature")
    if not isinstance(their_terms, dict) or not isinstance(their_nonce, str):
        raise CryptoError("agreement message missing terms/nonce")
    verify_terms(mine["terms"], their_terms)  # step 3a — exact equality first
    if not isinstance(their_signature, str) or not verify_agreement_signature(
        their_terms, their_nonce, their_signature
    ):
        raise CryptoError("agreement signature mismatch — refusing to play (INTEROP §4.3b)")
    _assert_pairing(sub_game_number, role, theirs)  # §7.2 pairing declaration guard

    identity = theirs.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    opponent_gid = identity.get("group_id")
    if not isinstance(opponent_gid, str) or not opponent_gid:
        raise CryptoError("opponent identity missing group_id — cannot derive game ids")
    my_gid = config.private("game.group_id")
    game_id, game_uid = derive_game_ids(their_terms, [my_gid, opponent_gid])
    counted = identity.get("counted_games_so_far")
    return Handshake(
        game_id=game_id,
        game_uid=game_uid,
        terms=their_terms,
        opponent_identity=identity,
        opponent_pubkey=identity.get("ed25519_public_key"),
        opponent_counted_games=counted if isinstance(counted, int) else None,
    )
