from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Any

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex
from pursuit.interface.board_view import CELL_PX, BoardView


def _uniform_belief(board_size: int) -> list[list[float]]:
    val = 1.0 / (board_size * board_size)
    return [[val] * board_size for _ in range(board_size)]


def _verify_record(record: dict[str, Any]) -> bool:
    """True iff sha256(canonical_bytes(payload)) matches the stored commit."""
    commit = record.get("commit")
    payload = record.get("payload")
    if not isinstance(commit, str) or not isinstance(payload, dict):
        return False
    return sha256_hex(canonical_bytes(payload)) == commit


class ReplayViewer:
    """Step-by-step replay of a sealed-log JSON file with commit verification."""

    def __init__(self, log_path: str | Path) -> None:
        self._log_path = Path(log_path)
        self._records: list[dict[str, Any]] = json.loads(
            self._log_path.read_text(encoding="utf-8")
        )
        self._verified = all(_verify_record(r) for r in self._records)

    def run(self) -> None:
        """Open the Tkinter window and run the interactive replay."""
        board_size = self._detect_board_size()
        belief = _uniform_belief(board_size)

        root = tk.Tk()
        root.title(f"Replay — {self._log_path.name}")
        root.resizable(False, False)

        banner_text = "VERIFIED OK" if self._verified else "AUDIT FAILED"
        banner_color = "#27ae60" if self._verified else "#c0392b"
        tk.Label(
            root, text=banner_text, bg=banner_color, fg="white",
            font=("Segoe UI", 12, "bold"), pady=6,
        ).pack(fill="x")

        board = BoardView(root, board_size)
        board.pack(padx=4, pady=4)

        info_var = tk.StringVar(value="Step 0")
        tk.Label(root, textvariable=info_var, font=("Segoe UI", 10)).pack()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=4)

        state = {"idx": 0}

        def _pos(raw: Any) -> tuple[int, int] | None:
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return (int(raw[0]), int(raw[1]))
            return None

        def show(idx: int) -> None:
            rec = self._records[idx]
            p = rec.get("payload", {})
            role = p.get("role", "")
            police_raw = p.get("police_pos") or (p.get("position") if role == "police" else None)
            thief_raw = p.get("thief_pos") or (p.get("position") if role == "thief" else None)
            barriers = [tuple(b) for b in p.get("barriers", []) if isinstance(b, (list, tuple))]
            thief_pos = _pos(thief_raw)
            board.render(
                my_pos=_pos(police_raw), role="police",
                barriers=barriers, visited=[],
                belief_matrix=belief,
                opponent_pos=thief_pos,
                opponent_role="thief" if thief_pos else None,
                message=p.get("message"),
            )
            info_var.set(f"Step {idx + 1} / {len(self._records)}")

        def prev_step() -> None:
            state["idx"] = max(0, state["idx"] - 1)
            show(state["idx"])

        def next_step() -> None:
            state["idx"] = min(len(self._records) - 1, state["idx"] + 1)
            show(state["idx"])

        tk.Button(btn_frame, text="< Prev", command=prev_step).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Next >", command=next_step).pack(side="left", padx=4)

        if self._records:
            show(0)

        if not self._verified:
            side = board_size * CELL_PX
            board.create_rectangle(0, side // 3, side, 2 * side // 3, fill="#c0392b", outline="")
            board.create_text(
                side // 2, side // 2, text="AUDIT FAILED",
                fill="white", font=("Segoe UI", 22, "bold"),
            )

        root.mainloop()

    def _detect_board_size(self) -> int:
        for rec in self._records:
            p = rec.get("payload", {})
            if isinstance(p, dict):
                size = p.get("board_size")
                if isinstance(size, int):
                    return size
        return 8
