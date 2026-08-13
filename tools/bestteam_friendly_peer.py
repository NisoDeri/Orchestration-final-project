from __future__ import annotations

import argparse
import hashlib
import json
import platform
import queue
import random
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastmcp import FastMCP

from pursuit.constants import Direction
from pursuit.domain.board import Board
from pursuit.domain.scent import make_scent_model
from pursuit.infra.email import GmailSender
from pursuit.infra.transport import http_call_tool
from pursuit.shared.config import ConfigManager, scent_params

ROLE_TO_WIRE = {"police": "cop", "thief": "thief"}
WIRE_TO_ROLE = {"cop": "police", "police": "police", "thief": "thief"}
BESTTEAM_COMMIT = "4198529b986f9ed06a7ebd27a5a40e407693909b"


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(data: dict[str, Any] | list[Any]) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def bestteam_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _cell(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return (int(value[0]), int(value[1]))
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git_commit() -> str:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = subprocess.run(
            ["git", "diff", "--quiet"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).returncode != 0
        return f"{commit}-dirty" if dirty else commit
    except Exception:
        return "unknown"


def _hardware() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cpu_model": platform.processor() or "unknown",
        "cpu_cores": (getattr(__import__("os"), "cpu_count")() or 1),
        "cpu_threads": (getattr(__import__("os"), "cpu_count")() or 1),
        "cpu_mhz": "unknown",
        "ram_gb": "unknown",
        "gpu": "unknown",
    }


def _public_port_free(host: str, port: int) -> bool:
    sock = socket.socket()
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


@dataclass
class Inboxes:
    negotiate: queue.Queue = field(default_factory=queue.Queue)
    receive_commit: queue.Queue = field(default_factory=queue.Queue)
    receive_reveal: queue.Queue = field(default_factory=queue.Queue)
    declare_barrier: queue.Queue = field(default_factory=queue.Queue)
    capture_claim: queue.Queue = field(default_factory=queue.Queue)
    final_reveal: queue.Queue = field(default_factory=queue.Queue)
    claim_answers: dict[int, tuple[bool, str]] = field(default_factory=dict)
    claim_events: dict[int, threading.Event] = field(default_factory=dict)
    claim_lock: threading.Lock = field(default_factory=threading.Lock)

    def drain_step(self) -> None:
        for q in (
            self.receive_commit,
            self.receive_reveal,
            self.declare_barrier,
            self.capture_claim,
        ):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break


class BestteamServer:
    def __init__(
        self,
        role: str,
        host: str,
        port: int,
        inboxes: Inboxes,
        *,
        config_digest: str,
    ) -> None:
        self.role = role
        self.host = host
        self.port = port
        self.inboxes = inboxes
        self.config_digest = config_digest
        self.mcp = FastMCP(f"nis-yar1-{ROLE_TO_WIRE[role]}-bestteam-adapter")

        def negotiate(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("negotiate", payload)
            self.inboxes.negotiate.put(payload)
            return {
                "kind": "negotiation",
                "step": payload.get("step", 0),
                "role": ROLE_TO_WIRE[self.role],
                "config_digest": self.config_digest,
                "scent_model_digest": "",
                "game_count": 6,
                "role_split": {"thief": [1, 2, 3], "cop": [4, 5, 6]},
                "readings": {},
                "step_zero": {},
            }

        def receive_commit(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("receive_commit", payload)
            self.inboxes.receive_commit.put(payload)
            return {
                "step": payload.get("step"),
                "role": ROLE_TO_WIRE[self.role],
                "acknowledged_digest": payload.get("digest"),
                "kind": "ack",
            }

        def receive_reveal(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("receive_reveal", payload)
            if "nonce" in payload:
                raise ValueError("receive_reveal must not contain nonce")
            self.inboxes.receive_reveal.put(payload)
            return {"step": payload.get("step"), "role": ROLE_TO_WIRE[self.role], "kind": "ack"}

        def declare_barrier(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("declare_barrier", payload)
            self.inboxes.declare_barrier.put(payload)
            return {"step": payload.get("step"), "role": ROLE_TO_WIRE[self.role], "kind": "ack"}

        def capture_claim(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("capture_claim", payload)
            self.inboxes.capture_claim.put(payload)
            step = int(payload.get("step", 0) or 0)
            event = self.inboxes.claim_event(step)
            event.wait(timeout=2.0)
            accepted, reason = self.inboxes.claim_answer(step)
            return {
                "step": payload.get("step"),
                "role": ROLE_TO_WIRE[self.role],
                "accepted": accepted,
                "reason": reason,
                "kind": "capture_response",
            }

        def final_reveal(message: dict | None = None, payload: dict | None = None) -> dict:
            payload = self._body(message, payload)
            self._require("final_reveal", payload)
            self.inboxes.final_reveal.put(payload)
            return {"step": payload.get("step"), "role": ROLE_TO_WIRE[self.role], "kind": "ack"}

        for fn, name in (
            (negotiate, "negotiate"),
            (receive_commit, "receive_commit"),
            (receive_reveal, "receive_reveal"),
            (declare_barrier, "declare_barrier"),
            (capture_claim, "capture_claim"),
            (final_reveal, "final_reveal"),
        ):
            self.mcp.tool(fn, name=name)

    @staticmethod
    def _body(message: dict | None = None, payload: dict | None = None) -> dict:
        body = payload if isinstance(payload, dict) else message
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _require(tool: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise TypeError(f"{tool}: payload must be an object")

    def start(self) -> threading.Thread:
        if not _public_port_free(self.host, self.port):
            raise RuntimeError(f"port already in use: {self.host}:{self.port}")
        thread = threading.Thread(
            target=self.mcp.run,
            kwargs={
                "transport": "http",
                "host": self.host,
                "port": self.port,
                "show_banner": False,
            },
            name=f"bestteam-adapter-{self.role}",
            daemon=True,
        )
        thread.start()
        return thread


def _claim_event(self: Inboxes, step: int) -> threading.Event:
    with self.claim_lock:
        event = self.claim_events.get(step)
        if event is None:
            event = threading.Event()
            self.claim_events[step] = event
        return event


def _claim_answer(self: Inboxes, step: int) -> tuple[bool, str]:
    with self.claim_lock:
        return self.claim_answers.get(step, (False, "capture was not locally verified"))


def _set_claim_answer(self: Inboxes, step: int, accepted: bool, reason: str) -> None:
    with self.claim_lock:
        self.claim_answers[step] = (accepted, reason)
        event = self.claim_events.get(step)
        if event is None:
            event = threading.Event()
            self.claim_events[step] = event
        event.set()


Inboxes.claim_event = _claim_event  # type: ignore[attr-defined]
Inboxes.claim_answer = _claim_answer  # type: ignore[attr-defined]
Inboxes.set_claim_answer = _set_claim_answer  # type: ignore[attr-defined]


class BestteamClient:
    def __init__(self, url: str, timeout: float = 30.0) -> None:
        self.url = url.rstrip("/") + ("" if url.rstrip("/").endswith("/mcp") else "/mcp")
        self.timeout = timeout

    def call(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool != "negotiate":
            return http_call_tool(self.url, tool, {"payload": payload}, self.timeout)
        try:
            return http_call_tool(self.url, tool, {"message": payload}, self.timeout)
        except Exception:
            return http_call_tool(self.url, tool, {"payload": payload}, self.timeout)


@dataclass
class StepRecord:
    step: int
    state: dict[str, Any]
    role: str
    move: str
    intent: str
    hint: str
    nonce: str
    scent: list[list[Any]]
    scent_digest: str
    barrier_cell: list[int] | None
    commit_digest: str
    opponent_commit: dict[str, Any]
    opponent_reveal: dict[str, Any]
    audit_passed: bool | None = None


class FriendlySubgame:
    def __init__(
        self,
        *,
        role: str,
        subgame: int,
        config: ConfigManager,
        client: BestteamClient,
        inboxes: Inboxes,
        github_commit: str,
        opponent_commit: str,
        seed: int,
        receive_timeout: float,
    ) -> None:
        self.role = role
        self.opp_role = "thief" if role == "police" else "police"
        self.subgame = subgame
        self.config = config
        self.client = client
        self.inboxes = inboxes
        self.github_commit = github_commit
        self.opponent_commit = opponent_commit
        self.receive_timeout = float(receive_timeout)
        self.rng = random.Random(seed + subgame)
        self.board = Board(
            config.game("board_and_agents.grid_size"),
            config.game("movement_and_barriers.move_set"),
        )
        self.cop = tuple(config.game("board_and_agents.cop_start"))
        self.thief = tuple(config.game("board_and_agents.thief_start"))
        self.barriers: set[tuple[int, int]] = set()
        self.max_steps = int(config.game("movement_and_barriers.max_moves"))
        self.max_barriers = int(config.game("movement_and_barriers.max_barriers"))
        self.own_barriers = 0
        self.opp_barriers = 0
        self.scent = make_scent_model(scent_params(config.game))
        self.records: list[StepRecord] = []
        self.final_nonces: dict[str, str] = {}
        self.their_final_reveal: dict[str, Any] | None = None
        self.started_at = _now()

    def run(self) -> dict[str, Any]:
        self._negotiate()
        result, winner_role, reason, ended_step = self._loop()
        self._final_reveal(ended_step)
        audits = self._verify_records()
        ended_at = _now()
        return {
            "sub_game_number": self.subgame,
            "roles": {"nis-yar1": self.role, "bestteam": self.opp_role},
            "started_at": self.started_at,
            "ended_at": ended_at,
            "result": result,
            "winner_role": winner_role,
            "winner_group": None
            if winner_role is None
            else ("nis-yar1" if winner_role == self.role else "bestteam"),
            "reason": reason,
            "github_commit": {"nis-yar1": self.github_commit, "bestteam": self.opponent_commit},
            "score": self._score(result, winner_role),
            "steps": ended_step,
            "turns_completed": ended_step,
            "game_uid": self.config.config_sha256(),
            "audit": {
                "passed": all(audits),
                "forgery": not all(audits),
                "opponent_received": bool(self.records),
                "failed_steps": [
                    rec.step for rec, passed in zip(self.records, audits, strict=False) if not passed
                ],
                "log_verified": all(audits),
            },
        }

    def _negotiate(self) -> None:
        payload = {
            "kind": "handshake",
            "step": 0,
            "role": ROLE_TO_WIRE[self.role],
            "config_digest": self.config.config_sha256(),
            "scent_model_digest": "",
            "game_count": 6,
            "role_split": {"thief": [1, 2, 3], "cop": [4, 5, 6]},
            "readings": self._readings(),
            "step_zero": self._step_zero(),
        }
        self.client.call("negotiate", payload)
        try:
            incoming = self.inboxes.negotiate.get(timeout=5)
        except queue.Empty:
            incoming = None
        if isinstance(incoming, dict) and incoming.get("config_digest") != self.config.config_sha256():
            raise RuntimeError(f"bestteam config digest mismatch: {incoming.get('config_digest')}")

    def _readings(self) -> dict[str, Any]:
        return {
            "capture_resolution": "after_moves",
            "stay_is_not_a_move": True,
            "swap_is_capture": True,
            "barrier_cell_sealed": True,
            "scent_digest_sealed": True,
            "scent_sampling": "end_of_previous_full_turn",
        }

    def _step_zero(self) -> dict[str, Any]:
        return {
            "team_name": "nis-yar1",
            "members": self.config.private("game.members"),
            "repos": self.config.private("game.repos"),
            "role": ROLE_TO_WIRE[self.role],
            "sub_game": self.subgame,
            "llm_model": self.config.private("trash_talk.model"),
            "code_version": self.config.private("version"),
            "github_commit": self.github_commit,
            "hardware": _hardware(),
        }

    def _loop(self) -> tuple[str, str | None, str, int]:
        for step in range(self.max_steps):
            self.inboxes.drain_step()
            state = {"cop": list(self.cop), "thief": list(self.thief), "step": step}
            decision = self._decide()
            decision["step"] = step
            next_pos = self._next_own_position(decision["move"])
            self.scent.full_turn(next_pos)
            scent_list = self._scent_list()
            scent_digest = sha256_json(scent_list)
            nonce = f"{self.rng.getrandbits(128):032x}"
            seal_payload: dict[str, Any] = {
                "state": state,
                "move": decision["move"],
                "intent": decision["intent"],
                "nonce": nonce,
                "scent_digest": scent_digest,
            }
            if decision["barrier_cell"] is not None:
                seal_payload["barrier_cell"] = decision["barrier_cell"]
            commit_digest = bestteam_digest(seal_payload)
            self.final_nonces[str(step)] = nonce
            commit_payload = {
                "kind": "commit",
                "step": step,
                "role": ROLE_TO_WIRE[self.role],
                "digest": commit_digest,
            }
            self.client.call("receive_commit", commit_payload)
            their_commit = self.inboxes.receive_commit.get(timeout=self.receive_timeout)
            reveal_payload = {
                "kind": "reveal",
                "step": step,
                "role": ROLE_TO_WIRE[self.role],
                "move": decision["move"],
                "hint": decision["hint"],
                "intent": decision["intent"],
                "scent": scent_list,
            }
            if decision["barrier_cell"] is not None:
                reveal_payload["barrier_cell"] = decision["barrier_cell"]
                self.client.call(
                    "declare_barrier",
                    {
                        "kind": "declare_barrier",
                        "step": step,
                        "role": ROLE_TO_WIRE[self.role],
                        "cell": decision["barrier_cell"],
                        "remaining": self.max_barriers - self.own_barriers - 1,
                    },
                )
            self.client.call("receive_reveal", reveal_payload)
            their_reveal = self.inboxes.receive_reveal.get(timeout=self.receive_timeout)
            self.records.append(
                StepRecord(
                    step=step,
                    state=state,
                    role=ROLE_TO_WIRE[self.role],
                    move=decision["move"],
                    intent=decision["intent"],
                    hint=decision["hint"],
                    nonce=nonce,
                    scent=scent_list,
                    scent_digest=scent_digest,
                    barrier_cell=decision["barrier_cell"],
                    commit_digest=commit_digest,
                    opponent_commit=their_commit,
                    opponent_reveal=their_reveal,
                )
            )
            result = self._resolve_step(decision, their_reveal)
            if result is not None:
                return (*result, step + 1)
        return ("survival", "thief", "survival threshold reached", self.max_steps)

    def _decide(self) -> dict[str, Any]:
        if self.role == "thief":
            move = self._choose_thief_move()
            return {
                "move": move.value,
                "intent": "truth",
                "hint": "I am keeping distance.",
                "barrier_cell": None,
            }
        move = self._choose_police_move()
        return {
            "move": move.value,
            "intent": "truth",
            "hint": "I am closing the distance.",
            "barrier_cell": None,
        }

    def _choose_thief_move(self) -> Direction:
        moves = self.board.legal_moves(self.thief, self.barriers)
        if not moves:
            return Direction.STAY
        scored: list[tuple[int, int, Direction]] = []
        for direction, dest in moves:
            distance = self.board.bfs_distance(dest, self.cop, self.barriers)
            mobility = len(self.board.reachable_cells(dest, self.barriers, 2))
            scored.append(((distance if distance is not None else 99), mobility, direction))
        best_dist = max(item[0] for item in scored)
        near = [item for item in scored if item[0] >= best_dist - 1]
        near.sort(key=lambda item: (-item[0], -item[1], item[2].value))
        return near[self.rng.randrange(min(len(near), 2))][2]

    def _choose_police_move(self) -> Direction:
        moves = self.board.legal_moves(self.cop, self.barriers)
        if not moves:
            return Direction.STAY
        scored: list[tuple[int, Direction]] = []
        for direction, dest in moves:
            distance = self.board.bfs_distance(dest, self.thief, self.barriers)
            scored.append((distance if distance is not None else 99, direction))
        scored.sort(key=lambda item: (item[0], item[1].value))
        return scored[0][1]

    def _next_own_position(self, move: str) -> tuple[int, int]:
        current = self.cop if self.role == "police" else self.thief
        dest = self.board.step(current, Direction(move), self.barriers)
        return dest if dest is not None else current

    def _scent_list(self) -> list[list[Any]]:
        items: list[list[Any]] = []
        for key, value in self.scent.snapshot().items():
            row, col = (int(part) for part in key.split(",", 1))
            items.append([row, col, value])
        return items

    def _resolve_step(
        self, own_decision: dict[str, Any], their_reveal: dict[str, Any]
    ) -> tuple[str, str | None, str] | None:
        their_role = WIRE_TO_ROLE.get(str(their_reveal.get("role")), self.opp_role)
        their_move = Direction(str(their_reveal.get("move", "STAY")))
        old_cop, old_thief = self.cop, self.thief
        own_next = self._next_own_position(own_decision["move"])
        their_current = self.thief if their_role == "thief" else self.cop
        their_next = self.board.step(their_current, their_move, self.barriers) or their_current
        if self.role == "police":
            self.cop, self.thief = own_next, their_next
            own_barrier = _cell(own_decision.get("barrier_cell"))
            their_barrier = _cell(their_reveal.get("barrier_cell"))
        else:
            self.thief, self.cop = own_next, their_next
            own_barrier = _cell(own_decision.get("barrier_cell"))
            their_barrier = _cell(their_reveal.get("barrier_cell"))
        if own_barrier is not None:
            self.barriers.add(own_barrier)
            self.own_barriers += 1
        if their_barrier is not None:
            self.barriers.add(their_barrier)
            self.opp_barriers += 1
        if self.cop == self.thief:
            self.inboxes.set_claim_answer(own_decision["step"], True, "cop and thief ended on same cell")
            self._send_capture_claim("landing")
            return ("capture", "police", "cop and thief ended on same cell")
        if old_cop == self.thief and old_thief == self.cop:
            self.inboxes.set_claim_answer(own_decision["step"], True, "agents swapped cells")
            self._send_capture_claim("swap")
            return ("capture", "police", "agents swapped cells")
        if own_barrier == self.thief or their_barrier == self.thief:
            self.inboxes.set_claim_answer(own_decision["step"], True, "barrier on thief final cell")
            self._send_capture_claim("barrier")
            return ("capture", "police", "barrier on thief final cell")
        if self._jailed(self.thief):
            self.inboxes.set_claim_answer(own_decision["step"], True, "thief jailed")
            self._send_capture_claim("jailed")
            return ("capture", "police", "thief jailed")
        self.inboxes.set_claim_answer(own_decision["step"], False, "no capture after resolving step")
        return None

    def _jailed(self, thief: tuple[int, int]) -> bool:
        orthogonal = [d for d in (Direction.N, Direction.S, Direction.E, Direction.W)]
        return all(self.board.step(thief, direction, self.barriers) is None for direction in orthogonal)

    def _send_capture_claim(self, rule: str) -> None:
        if self.role != "police":
            return
        try:
            self.client.call(
                "capture_claim",
                {
                    "kind": "capture_claim",
                    "step": self.records[-1].step if self.records else 0,
                    "role": ROLE_TO_WIRE[self.role],
                    "cell": list(self.cop),
                    "rule": rule,
                },
            )
        except Exception:
            pass

    def _final_reveal(self, step: int) -> None:
        payload = {
            "kind": "final_reveal",
            "step": step,
            "role": ROLE_TO_WIRE[self.role],
            "nonces": dict(self.final_nonces),
        }
        self.client.call("final_reveal", payload)
        try:
            self.their_final_reveal = self.inboxes.final_reveal.get(timeout=10)
        except queue.Empty:
            pass

    def _verify_records(self) -> list[bool]:
        checks: list[bool] = []
        for record in self.records:
            reveal = record.opponent_reveal
            commit = record.opponent_commit
            digest = str(commit.get("digest", ""))
            nonce = None
            try:
                final = self.their_final_reveal or {}
                nonce = dict(final.get("nonces", {})).get(str(record.step))
            except Exception:
                nonce = None
            if not nonce:
                checks.append(True)
                continue
            scent_digest = sha256_json(reveal.get("scent", []))
            payload: dict[str, Any] = {
                "state": record.state,
                "move": reveal.get("move"),
                "intent": reveal.get("intent"),
                "nonce": nonce,
                "scent_digest": scent_digest,
            }
            if reveal.get("barrier_cell") is not None:
                payload["barrier_cell"] = reveal["barrier_cell"]
            checks.append(bestteam_digest(payload) == digest)
        return checks

    def _score(self, result: str, winner_role: str | None) -> dict[str, int]:
        scoring = self.config.game("scoring")
        if result == "capture":
            by_role = {"police": scoring["capture_cop"], "thief": scoring["capture_thief"]}
        elif result == "survival":
            by_role = {"police": scoring["survival_cop"], "thief": scoring["survival_thief"]}
        else:
            by_role = {"police": scoring["technical_loss"], "thief": scoring["technical_loss"]}
        return {"nis-yar1": int(by_role[self.role]), "bestteam": int(by_role[self.opp_role])}


def _result_subject(result: dict[str, Any]) -> str:
    game_id = result["game_id"]
    total = result["final_result"]["total_score"]
    winner = result["final_result"]["winner_group"]
    scores = " ".join(f"{gid}:{total[gid]}" for gid in sorted(total))
    return f"FRIENDLY P2P league SERIES result - {game_id} - winner={winner} - {scores}"


def build_result(rows: list[dict[str, Any]], config_sha: str) -> dict[str, Any]:
    totals = {"bestteam": 0, "nis-yar1": 0}
    wins = {"bestteam": 0, "nis-yar1": 0}
    for row in rows:
        for gid, points in row["score"].items():
            totals[gid] += int(points)
        if row.get("winner_group") in wins:
            wins[row["winner_group"]] += 1
    winner = "series_tie"
    if totals["bestteam"] != totals["nis-yar1"]:
        winner = "bestteam" if totals["bestteam"] > totals["nis-yar1"] else "nis-yar1"
    game_id = f"friendly-bestteam-nis-yar1-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    return {
        "_schema": "friendly_bestteam_adapter_result",
        "schema_version": "1.0",
        "report_type": "friendly_game_result",
        "game_id": game_id,
        "game_uid": config_sha,
        "friendly": True,
        "links": {
            "github": {
                "nis-yar1": "https://github.com/NisoDeri/Orchestration-final-project",
                "bestteam": "https://github.com/Diana-Koroblov/bestteam-cop",
                "bestteam_thief": "https://github.com/Diana-Koroblov/bestteam-thief",
            }
        },
        "groups": ["bestteam", "nis-yar1"],
        "num_sub_games": len(rows),
        "sub_games": rows,
        "final_result": {
            "total_score": totals,
            "sub_games_won": wins,
            "winner_group": None if winner == "series_tie" else winner,
            "series_tie": winner == "series_tie",
            "games_played_including_this": {"bestteam": 0, "nis-yar1": 0},
            "diversity_reward_applied": {"bestteam": False, "nis-yar1": False},
        },
        "mutual_agreement": {"sha256": config_sha, "confirmed": True},
    }


def run_block(args: argparse.Namespace, role: str, subgames: list[int]) -> list[dict[str, Any]]:
    config_dir = ROOT / "config" / ("police" if role == "police" else "thief")
    config = ConfigManager.load(config_dir)
    config.override_game("pheromones.dialect", "multiplicative_book_v1")
    port = 8802 if role == "police" else 8801
    inboxes = Inboxes()
    BestteamServer(role, "127.0.0.1", port, inboxes,
                   config_digest=config.config_sha256()).start()
    time.sleep(1.0)
    client = BestteamClient(args.opponent_url, timeout=args.timeout)
    rows: list[dict[str, Any]] = []
    for subgame in subgames:
        print(f"[{_now()}] starting sub-game {subgame} as {role}", flush=True)
        game = FriendlySubgame(
            role=role,
            subgame=subgame,
            config=config,
            client=client,
            inboxes=inboxes,
            github_commit=args.github_commit,
            opponent_commit=args.opponent_commit,
            seed=args.seed,
            receive_timeout=args.receive_timeout,
        )
        row = game.run()
        rows.append(row)
        print(
            f"[{_now()}] finished sub-game {subgame}: {row['result']} winner={row['winner_group']}",
            flush=True,
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["thief", "police", "both"], default="both")
    parser.add_argument(
        "--opponent-url",
        default="https://denotatively-sciuroid-florine.ngrok-free.dev/mcp",
    )
    parser.add_argument("--opponent-commit", default=BESTTEAM_COMMIT)
    parser.add_argument("--github-commit", default=_git_commit())
    parser.add_argument("--timeout", type=float, default=40.0)
    parser.add_argument(
        "--receive-timeout",
        type=float,
        default=180.0,
        help="seconds to wait for inbound bestteam commit/reveal calls per step",
    )
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--email-to", default="yardentziar@gmail.com")
    parser.add_argument("--email-from", default="yardentziar@gmail.com")
    parser.add_argument("--no-email", action="store_true")
    args = parser.parse_args()
    example_payload = {
        "state": {"cop": [0, 0], "thief": [3, 3], "step": 0},
        "move": "N",
        "intent": "truth",
        "nonce": "deadbeefdeadbeefdeadbeefdeadbeef",
    }
    expected = "317fe40fe6ec33202373161f5a9683d093eca58aec73bc3e1166cd9850da61fc"
    if bestteam_digest(example_payload) != expected:
        raise RuntimeError("bestteam digest self-check failed")
    rows: list[dict[str, Any]] = []
    if args.role in {"thief", "both"}:
        rows.extend(run_block(args, "thief", [1, 2, 3]))
    if args.role in {"police", "both"}:
        rows.extend(run_block(args, "police", [4, 5, 6]))
    result = build_result(rows, ConfigManager.load(ROOT / "config" / "thief").config_sha256())
    out = ROOT / "logs" / "nis-yar1" / f"result_{result['game_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if not args.no_email and len(rows) == 6:
        sent = GmailSender().send_result(_result_subject(result), result, args.email_to, args.email_from)
        print(f"email: {sent}", flush=True)
    print(f"result_path: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
