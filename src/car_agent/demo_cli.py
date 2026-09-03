"""Offline happy-path demo for a clean checkout."""

from __future__ import annotations

from .crewai_agent import CrewAISalesAgent


DEMO_TURNS = [
    "I want something under $45k.",
    "It will be a weekend car for spirited driving, preferably a coupe.",
    "What should I inspect on the Honda S2000?",
    "Please schedule a test drive for the Honda S2000.",
    "My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.",
]


def main() -> int:
    sales_agent = CrewAISalesAgent(use_live_model=False)
    conversation_id = "phase4-demo"
    final_stage = ""
    print("Classic Sports Car Agent — offline demo")
    for shopper_message in DEMO_TURNS:
        response = sales_agent.respond(conversation_id, shopper_message)
        final_stage = response.state.stage
        tool_names = ", ".join(call.name for call in response.trace) or "none"
        print(f"\nshopper> {shopper_message}")
        print(f"agent> {response.message}")
        print(f"stage: {response.state.stage}")
        print(f"tools: {tool_names}")
    print(f"\nDemo result: {'PASS' if final_stage == 'scheduled' else 'FAIL'}")
    return 0 if final_stage == "scheduled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
