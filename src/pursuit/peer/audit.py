"""End-game mutual audit exchange (architecture §2 ``peer/audit.py``; rulings A6/A8/A9).

Runs on EVERY ending — capture, survival, timeout, crash, breach (D4; fixes reference
gap #5): we always push our own reveal (best-effort, the transport suppresses expiry),
then wait one bounded window for theirs. A missing opponent payload is legal (INTEROP
§2.3 — the winner may exit first) and is NOT forgery; a revealed record whose commit
does not recompute, or a step-0 declaration whose D14 Ed25519 signature fails against
the pubkey locked at the handshake, IS provable forgery → the caller adjudicates
``technical_loss`` 0/0 and both groups must report it (ruling A9a).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pursuit.constants import GameResult, Role
from pursuit.domain.protocol_audit import AuditPayload, AuditRecord
from pursuit.exceptions import DeadlineError, TransportError
from pursuit.peer.sealing import SealedLog, verify_step0_signature


@dataclass(frozen=True)
class SubgameOutcome:
    """One finished, audit-adjudicated sub-game — everything the series driver needs."""

    result: GameResult
    winner: Role | None
    scores: dict[Role, int]  # straight from the signed scoring config (Table 17)
    audit: dict[str, Any]
    records: list[dict[str, Any]]  # my sealed chain, nonces revealed (post-audit)
    steps: int  # my OWN step counter (ruling A5)
    game_id: str
    game_uid: str
    opponent_group: str


def exchange_audits(role: Role, result: GameResult, log: SealedLog, transport: Any,
                    audits_inbox: Any, deadlines: Any, audit_timeout: float,
                    opponent_pubkey: str | None) -> dict[str, Any]:
    """A8 stage 4: reveal every nonce both ways; verify theirs; report per-step results.

    Returns the audit dict for the log summary: ``passed`` / ``forgery`` /
    ``opponent_received`` / ``steps`` / ``failed_steps`` (+ ``their_claim`` when the
    opponent's payload arrived).
    """
    mine = AuditPayload(sender=role.value, result_claim=result.value,
                        records=[AuditRecord(**rec) for rec in log.audit_reveal()])
    transport.submit_audit(mine.to_wire())  # best-effort: errors suppressed on expiry
    audit: dict[str, Any] = {"passed": False, "forgery": False,
                             "opponent_received": False, "steps": [], "failed_steps": []}
    deadlines.arm("audit-exchange", audit_timeout)
    try:
        theirs = AuditPayload.from_wire(audits_inbox.get(timeout=audit_timeout))
    except (DeadlineError, TransportError):
        return audit  # opponent may have exited (INTEROP §2.3) — absence != forgery
    finally:
        deadlines.disarm("audit-exchange")
    steps = SealedLog.audit_verify([rec.to_wire() for rec in theirs.records], log.dialect)
    failed = [step["step"] for step in steps if not step["ok"]]
    if not failed and opponent_pubkey and theirs.records and not verify_step0_signature(
            theirs.records[0].payload, opponent_pubkey.encode("ascii")):
        failed = [0]  # forged D14 hardware/ledger declaration (rulings A7/A9b)
    audit.update(passed=not failed, forgery=bool(failed), opponent_received=True,
                 steps=steps, failed_steps=failed, their_claim=theirs.result_claim)
    return audit
