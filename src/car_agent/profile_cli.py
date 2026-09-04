"""CLI latency profile for the offline deterministic sales path."""

from __future__ import annotations

import argparse

from .agent import DemoSalesAgent
from .profiling import TimingRecorder, TimingSummary
from .tools import SalesTools


PROFILE_TURNS = (
    "I want something under $45k.",
    "It will be a weekend car for spirited driving, preferably a coupe.",
    "Do you have a 2011 BMW M3 in inventory?",
    "What should I inspect on the Honda S2000?",
    "Please schedule a test drive for the Honda S2000.",
    "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.",
)


def run_profile(iterations: int = 25) -> tuple[TimingRecorder, int]:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    recorder = TimingRecorder()
    tools = SalesTools()
    for iteration in range(iterations):
        agent = DemoSalesAgent(tools=tools, profiler=recorder)
        conversation_id = f"latency-profile-{iteration}"
        for message in PROFILE_TURNS:
            agent.respond(conversation_id, message)
    return recorder, iterations * len(PROFILE_TURNS)


def format_profile(recorder: TimingRecorder, turn_count: int, iterations: int) -> str:
    wall_time_ms = recorder.root_total_ms
    lines = [
        "Offline latency profile (deterministic path)",
        f"workload: {iterations} runs × {len(PROFILE_TURNS)} turns = {turn_count} turns",
        f"measured agent wall time: {wall_time_ms:.2f} ms",
        "",
        "Exclusive time excludes nested tool/flow spans; the agent.turn row is residual routing/formatting time.",
        f"{'Phase':<38} {'Calls':>7} {'Exclusive ms':>14} {'Avg ms':>10} {'Share':>8}",
        "-" * 80,
    ]
    summaries = sorted(
        recorder.summaries(),
        key=lambda summary: summary.exclusive_ms,
        reverse=True,
    )
    for summary in summaries:
        share = (summary.exclusive_ms / wall_time_ms * 100) if wall_time_ms else 0.0
        lines.append(_format_summary(summary, share))
    return "\n".join(lines)


def _format_summary(summary: TimingSummary, share: float) -> str:
    return f"{summary.name:<38} {summary.calls:>7} {summary.exclusive_ms:>12.2f} {summary.average_ms:>10.3f} {share:>7.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile offline sales-agent latency by phase")
    parser.add_argument("--iterations", type=int, default=25, help="Number of times to repeat the five-turn flow")
    args = parser.parse_args()
    recorder, turn_count = run_profile(args.iterations)
    print(format_profile(recorder, turn_count, args.iterations))


if __name__ == "__main__":
    main()
