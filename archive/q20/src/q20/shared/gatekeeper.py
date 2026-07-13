"""Centralized API gatekeeper — the single chokepoint for every external call.

Every model/tool call routes through ``Gatekeeper.execute(...)``. Even with the
local Ollama engine (free, generous limits) this path is always used, so behavior
is identical — and correct — the instant the engine is swapped to a metered cloud
model. Responsibilities: enforce per-service rate limits, bound concurrency, retry
transient failures with backoff, track cost/effort, log calls.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from q20.shared.cost import CostTracker, Usage

logger = logging.getLogger("q20.gatekeeper")


@dataclass(frozen=True)
class ServiceLimits:
    """Rate/retry policy for one logical service, sourced from config."""

    requests_per_minute: int
    concurrent_max: int
    retry_after_seconds: float
    max_retries: int


class _SlidingWindow:
    """Thread-safe per-minute sliding-window rate limiter."""

    def __init__(self, max_per_minute: int):
        self._max = max_per_minute
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def time_until_slot(self) -> float:
        """Reserve a slot if free (return 0), else seconds to wait for the next."""
        with self._lock:
            now = time.monotonic()
            while self._events and now - self._events[0] >= 60.0:
                self._events.popleft()
            if len(self._events) < self._max:
                self._events.append(now)
                return 0.0
            return 60.0 - (now - self._events[0])


class Gatekeeper:
    """Routes all external calls through rate-limiting, retry, and cost tracking."""

    def __init__(self, limits: dict[str, ServiceLimits], cost: CostTracker):
        self._limits = limits
        self._cost = cost
        self._windows: dict[str, _SlidingWindow] = {}
        self._sems: dict[str, threading.Semaphore] = {}
        self._lock = threading.Lock()

    def _resources(self, service: str):
        with self._lock:
            if service not in self._limits:
                service = "default"
            if service not in self._windows:
                lim = self._limits[service]
                self._windows[service] = _SlidingWindow(lim.requests_per_minute)
                self._sems[service] = threading.Semaphore(lim.concurrent_max)
            return service, self._limits[service], self._windows[service], self._sems[service]

    def execute(
        self,
        fn: Callable[..., Any],
        *args: Any,
        service: str = "default",
        usage_of: Callable[[Any], Usage] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run ``fn(*args, **kwargs)`` under the named service's limits and tracking.

        ``usage_of`` optionally extracts a ``Usage`` from the result for cost
        accounting (used for cloud engines; local calls report zero-cost usage).
        """
        service, lim, window, sem = self._resources(service)
        sem.acquire()  # bounds concurrency; callers queue here when full
        try:
            return self._run_with_retry(fn, args, kwargs, lim, window, service, usage_of)
        finally:
            sem.release()

    def _run_with_retry(self, fn, args, kwargs, lim, window, service, usage_of):
        attempt = 0
        while True:
            wait = window.time_until_slot()
            if wait > 0:
                time.sleep(min(wait, lim.retry_after_seconds))
                continue
            started = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - classify by retry budget
                attempt += 1
                if attempt > lim.max_retries:
                    logger.error("service=%s failed after %d retries: %s", service, attempt - 1, exc)
                    raise
                backoff = lim.retry_after_seconds * attempt
                logger.warning("service=%s attempt %d failed (%s); backoff %.1fs",
                               service, attempt, exc, backoff)
                time.sleep(backoff)
                continue
            elapsed = time.monotonic() - started
            usage = usage_of(result) if usage_of else Usage()
            self._cost.record(service, usage, elapsed)
            logger.info("service=%s ok %.2fs tokens=%d cost=$%.4f",
                        service, elapsed, usage.total, self._cost.last_cost)
            return result

    @property
    def cost_report(self) -> dict[str, dict]:
        return self._cost.report()
