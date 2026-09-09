"""Timing utilities."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator


@dataclass
class _ActiveSpan:
    name: str
    started: float
    child_seconds: float = 0.0


@dataclass(frozen=True)
class TimingSpan:
    name: str
    duration_ms: float
    exclusive_ms: float
    parent: str | None


@dataclass(frozen=True)
class TimingSummary:
    name: str
    calls: int
    total_ms: float
    exclusive_ms: float

    @property
    def average_ms(self) -> float:
        return self.total_ms / self.calls if self.calls else 0.0


class TimingRecorder:
    """Record timing spans when enabled."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.spans: list[TimingSpan] = []
        self._stack: list[_ActiveSpan] = []

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        active = _ActiveSpan(name=name, started=perf_counter())
        parent = self._stack[-1] if self._stack else None
        self._stack.append(active)
        try:
            yield
        finally:
            duration_seconds = perf_counter() - active.started
            self._stack.pop()
            self.spans.append(
                TimingSpan(
                    name=name,
                    duration_ms=duration_seconds * 1000,
                    exclusive_ms=max(0.0, (duration_seconds - active.child_seconds) * 1000),
                    parent=parent.name if parent else None,
                )
            )
            if parent:
                parent.child_seconds += duration_seconds

    def reset(self) -> None:
        self.spans.clear()
        self._stack.clear()

    def summaries(self) -> list[TimingSummary]:
        grouped: dict[str, list[float]] = {}
        for span in self.spans:
            values = grouped.setdefault(span.name, [0.0, 0.0, 0.0])
            values[0] += 1
            values[1] += span.duration_ms
            values[2] += span.exclusive_ms
        return [
            TimingSummary(name=name, calls=int(values[0]), total_ms=values[1], exclusive_ms=values[2])
            for name, values in grouped.items()
        ]

    @property
    def root_total_ms(self) -> float:
        return sum(span.duration_ms for span in self.spans if span.parent is None)
