"""CLI latency profile for offline and live sales-agent paths."""

from __future__ import annotations

import argparse

from .agent import DeterministicRouter
from .crewai_agent import CrewAISalesAgent
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

LIVE_PROFILE_TURNS = (
    "I want something under $45k.",
    "It will be a weekend car for spirited driving, preferably a coupe.",
    "Do you have a 2011 BMW M3 in inventory?",
    "What should I inspect on the Honda S2000?",
)


def run_profile(iterations: int = 25) -> tuple[TimingRecorder, int]:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    recorder = TimingRecorder()
    tools = SalesTools()
    for iteration in range(iterations):
        agent = DeterministicRouter(tools=tools, profiler=recorder)
        conversation_id = f"latency-profile-{iteration}"
        for message in PROFILE_TURNS:
            agent.respond(conversation_id, message)
    return recorder, iterations * len(PROFILE_TURNS)


def run_live_profile(iterations: int = 1) -> tuple[TimingRecorder, int, str]:
    """Run a deliberately small live workload that makes real provider calls."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    recorder = TimingRecorder()
    agent = CrewAISalesAgent(use_live_model=True, profiler=recorder)
    for iteration in range(iterations):
        conversation_id = f"live-latency-profile-{iteration}"
        for message in LIVE_PROFILE_TURNS:
            agent.respond(conversation_id, message)
    return recorder, iterations * len(LIVE_PROFILE_TURNS), agent.llm


def format_profile(recorder: TimingRecorder, turn_count: int, iterations: int) -> str:
    wall_time_ms = recorder.root_total_ms
    lines = [
        "Offline latency profile (deterministic router path)",
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


def format_live_profile(recorder: TimingRecorder, turn_count: int, iterations: int, model: str) -> str:
    wall_time_ms = sum(
        summary.total_ms
        for summary in recorder.summaries()
        if summary.name == "crewai.live_turn"
    )
    lines = [
        "Live latency profile (CrewAI + OpenRouter)",
        f"model: {model}",
        f"workload: {iterations} runs × {len(LIVE_PROFILE_TURNS)} turns = {turn_count} turns",
        f"measured live turn wall time: {wall_time_ms:.2f} ms",
        "",
        "crew kickoff includes model requests, CrewAI orchestration, and tool scheduling.",
        "Exclusive time excludes nested spans; crewai.live_turn is residual facade time.",
        f"{'Phase':<38} {'Calls':>7} {'Exclusive ms':>14} {'Avg ms':>10} {'Share':>8}",
        "-" * 80,
    ]
    summaries = sorted(recorder.summaries(), key=lambda summary: summary.exclusive_ms, reverse=True)
    for summary in summaries:
        share = (summary.exclusive_ms / wall_time_ms * 100) if wall_time_ms else 0.0
        lines.append(_format_summary(summary, share))
    return "\n".join(lines)


def _format_summary(summary: TimingSummary, share: float) -> str:
    return f"{summary.name:<38} {summary.calls:>7} {summary.exclusive_ms:>14.2f} {summary.average_ms:>10.3f} {share:>7.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile sales-agent latency by phase")
    parser.add_argument("--live", action="store_true", help="Make real CrewAI/OpenRouter calls")
    parser.add_argument("--iterations", type=int, default=None, help="Number of times to repeat the profile workload")
    args = parser.parse_args()
    iterations = args.iterations if args.iterations is not None else (1 if args.live else 25)
    if args.live:
        recorder, turn_count, model = run_live_profile(iterations)
        print(format_live_profile(recorder, turn_count, iterations, model))
    else:
        recorder, turn_count = run_profile(iterations)
        print(format_profile(recorder, turn_count, iterations))


if __name__ == "__main__":
    main()
