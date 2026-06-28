"""Cost & effort tracking.

Token-to-USD pricing per model; local engines (Ollama) are priced at $0. Even then
we always track call counts and wall-clock seconds, so "effort" is reported
regardless of engine — and the moment a metered cloud model is used, the dollar
accounting is already correct and the per-run cap is enforced.
"""

import threading
from dataclasses import dataclass

# USD per 1,000,000 tokens, as (input_price, output_price).
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.8, 4.0),
    "claude-opus-4-8": (5.0, 25.0),
    "ollama": (0.0, 0.0),
}


@dataclass
class Usage:
    """Token usage reported by a single model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "ollama"

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class _Acc:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    usd: float = 0.0


class CostTracker:
    """Thread-safe accumulator of cost + effort, with a per-run dollar cap."""

    def __init__(self, max_usd_per_run: float):
        self._max = max_usd_per_run
        self._by_service: dict[str, _Acc] = {}
        self._lock = threading.Lock()
        self.last_cost = 0.0

    @staticmethod
    def price(usage: Usage) -> float:
        """USD for a single usage record; matches model name by prefix/substring."""
        for key, (p_in, p_out) in PRICING.items():
            if usage.model.startswith(key) or key in usage.model:
                return (usage.input_tokens * p_in + usage.output_tokens * p_out) / 1_000_000
        return 0.0  # unknown/local model -> free

    def record(self, service: str, usage: Usage, seconds: float) -> None:
        """Record one call; raise if cumulative run cost exceeds the cap."""
        from q20.shared.exceptions import CostCapExceededError

        cost = self.price(usage)
        with self._lock:
            acc = self._by_service.setdefault(service, _Acc())
            acc.calls += 1
            acc.input_tokens += usage.input_tokens
            acc.output_tokens += usage.output_tokens
            acc.seconds += seconds
            acc.usd += cost
            self.last_cost = cost
            total = sum(a.usd for a in self._by_service.values())
        if total > self._max:
            raise CostCapExceededError(f"run cost ${total:.4f} exceeds cap ${self._max:.2f}")

    def report(self) -> dict[str, dict]:
        """Snapshot of per-service totals (calls, tokens, seconds, USD)."""
        with self._lock:
            return {svc: vars(acc).copy() for svc, acc in self._by_service.items()}

    def total_usd(self) -> float:
        with self._lock:
            return sum(a.usd for a in self._by_service.values())
