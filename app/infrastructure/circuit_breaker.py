from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class _Circuit:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    opened_at: float = 0
    half_open_inflight: int = 0


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, open_seconds: float = 30, half_open_probe_count: int = 1) -> None:
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.half_open_probe_count = half_open_probe_count
        self._circuits: dict[str, _Circuit] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        async with self._lock:
            circuit = self._circuits.setdefault(key, _Circuit())
            if circuit.state == CircuitState.OPEN and monotonic() - circuit.opened_at >= self.open_seconds:
                circuit.state = CircuitState.HALF_OPEN
                circuit.half_open_inflight = 0
            if circuit.state == CircuitState.OPEN:
                return False
            if circuit.state == CircuitState.HALF_OPEN:
                if circuit.half_open_inflight >= self.half_open_probe_count:
                    return False
                circuit.half_open_inflight += 1
            return True

    async def success(self, key: str) -> None:
        async with self._lock:
            self._circuits[key] = _Circuit()

    async def failure(self, key: str) -> None:
        async with self._lock:
            circuit = self._circuits.setdefault(key, _Circuit())
            circuit.failures += 1
            circuit.half_open_inflight = max(0, circuit.half_open_inflight - 1)
            if circuit.state == CircuitState.HALF_OPEN or circuit.failures >= self.failure_threshold:
                circuit.state = CircuitState.OPEN
                circuit.opened_at = monotonic()

    def state(self, key: str) -> CircuitState:
        return self._circuits.get(key, _Circuit()).state
