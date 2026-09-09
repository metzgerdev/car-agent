"""Interactive verifier for the Phase 1 acceptance cases."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from .crewai_agent import CrewAISalesAgent
from .models import AgentResponse, ToolCall


@dataclass
class VerificationCheck:
    case_id: str
    description: str
    passed: bool = False


class Phase1Verifier:
    """Runs real agent turns and accumulates Phase 1 acceptance evidence."""

    def __init__(self, agent: CrewAISalesAgent | None = None, conversation_id: str = "phase1-cli") -> None:
        self.agent = agent or CrewAISalesAgent(use_live_model=False)
        self.conversation_id = conversation_id
        self.last_response: AgentResponse | None = None
        self.turns: list[tuple[str, AgentResponse]] = []
        self.checks = self._new_checks()

    @staticmethod
    def _new_checks() -> dict[str, VerificationCheck]:
        return {
            "P1-T1": VerificationCheck("P1-T1", "qualification happens before tool use"),
            "P1-T2": VerificationCheck("P1-T2", "recommendation emits the ordered multi-tool trace"),
            "P1-T3": VerificationCheck("P1-T3", "vehicle facts are grounded and sourced"),
            "P1-T4": VerificationCheck("P1-T4", "valid details create exactly one test-drive request"),
            "P1-T5": VerificationCheck("P1-T5", "recommendation results respect the budget cap"),
        }

    @property
    def complete(self) -> bool:
        return all(check.passed for check in self.checks.values())

    def send(self, message: str) -> AgentResponse:
        response = self.agent.respond(self.conversation_id, message)
        self.last_response = response
        self.turns.append((message, response))
        self._observe(message, response)
        return response

    def reset(self) -> None:
        self.agent = CrewAISalesAgent(use_live_model=False)
        self.last_response = None
        self.turns = []
        self.checks = self._new_checks()

    def report(self) -> list[dict[str, Any]]:
        return [
            {
                "case_id": check.case_id,
                "description": check.description,
                "status": "PASS" if check.passed else "PENDING",
            }
            for check in self.checks.values()
        ]

    def _observe(self, message: str, response: AgentResponse) -> None:
        trace_names = [call.name for call in response.trace]
        if response.state.stage == "qualifying" and not response.trace:
            self.checks["P1-T1"].passed = True

        expected_trace = [
            "list_inventory",
            "get_vehicle",
            "get_vehicle",
            "get_vehicle_facts",
        ]
        if response.state.stage == "recommending" and trace_names == expected_trace:
            self.checks["P1-T2"].passed = True

        if self._is_fact_question(message):
            self.checks["P1-T3"].passed = self._has_grounded_facts(response)

        schedule_calls = [call for call in response.trace if call.name == "create_test_drive"]
        if schedule_calls:
            result = schedule_calls[-1].result
            self.checks["P1-T4"].passed = bool(
                result.get("ok") and len(self.agent.tools.scheduler.requests) == 1
            )

        search_calls = [call for call in response.trace if call.name == "list_inventory"]
        if search_calls and response.state.preferences.budget_max is not None:
            vehicles = search_calls[-1].result.get("vehicles", [])
            self.checks["P1-T5"].passed = all(
                vehicle.get("price", 0) <= response.state.preferences.budget_max for vehicle in vehicles
            )

    @staticmethod
    def _is_fact_question(message: str) -> bool:
        lowered = message.lower()
        return any(word in lowered for word in ("inspect", "inspection", "ownership", "maintenance", "service"))

    @staticmethod
    def _has_grounded_facts(response: AgentResponse) -> bool:
        fact_calls = [call for call in response.trace if call.name == "get_vehicle_facts"]
        if not fact_calls:
            return False
        for call in fact_calls:
            vehicle_id = call.arguments.get("vehicle_id")
            facts = call.result.get("facts", [])
            if not facts or any(
                fact.get("vehicle_id") != vehicle_id or not fact.get("source") for fact in facts
            ):
                return False
        return True


def _print_checks(verifier: Phase1Verifier) -> None:
    print("\nPhase 1 checks:")
    for check in verifier.report():
        marker = "PASS" if check["status"] == "PASS" else "...."
        print(f"  [{marker}] {check['case_id']} — {check['description']}")
    passed = sum(check["status"] == "PASS" for check in verifier.report())
    print(f"  {passed}/{len(verifier.checks)} checks passing")


def _print_trace(trace: list[ToolCall]) -> None:
    if not trace:
        print("  (no tool calls)")
        return
    for call in trace:
        if call.name == "list_inventory":
            detail = f"{call.result.get('count', 0)} vehicle(s)"
        elif call.name == "get_vehicle":
            detail = call.result.get("vehicle", {}).get("name", "not found")
        elif call.name == "get_vehicle_facts":
            detail = f"{call.result.get('source_count', 0)} source(s)"
        elif call.name == "get_service_history":
            detail = f"{call.result.get('record_count', 0)} service record(s)"
        elif call.name == "get_vehicle_comparison":
            detail = f"{len(call.result.get('vehicles', []))} vehicle(s)"
        elif call.name == "create_test_drive":
            detail = "request created" if call.result.get("ok") else "rejected"
        else:
            detail = "completed"
        print(f"  - {call.name}: {detail}")


def _print_guidance() -> None:
    print(
        "\nGuided Phase 1 flow (use the same conversation):\n"
        "  1. I want something under $45k.\n"
        "  2. It will be a weekend car for spirited driving, preferably a coupe.\n"
        "  3. What should I inspect on the Honda S2000?\n"
        "  4. Please schedule a test drive for the Honda S2000.\n"
        "  5. My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.\n"
        "\nCommands: /check  /state  /trace  /reset  /help  /quit\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactively verify the Phase 1 car-agent flow")
    parser.add_argument("--conversation-id", default="phase1-cli")
    parser.add_argument("--guided", action="store_true", help="print the recommended Phase 1 input sequence")
    parser.add_argument("--strict", action="store_true", help="exit 1 unless every check passes")
    args = parser.parse_args(argv)

    verifier = Phase1Verifier(conversation_id=args.conversation_id)
    print("Classic Sports Car Agent — Phase 1 verifier")
    print("Type a shopper message, or /help for commands.")
    if args.guided:
        _print_guidance()

    while True:
        try:
            raw = input("shopper> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        command = raw.lower()
        if command in {"/quit", "/exit", ":q"}:
            break
        if command == "/help":
            print("Commands: /check, /state, /trace, /reset, /help, /quit")
            continue
        if command == "/check":
            _print_checks(verifier)
            continue
        if command == "/state":
            if verifier.last_response:
                print(json.dumps(verifier.last_response.state.to_dict(redact_sensitive=True), indent=2))
            else:
                print("  (no conversation state yet)")
            continue
        if command == "/trace":
            _print_trace(verifier.last_response.trace if verifier.last_response else [])
            continue
        if command == "/reset":
            verifier.reset()
            print("Conversation and checks reset.")
            continue

        response = verifier.send(raw)
        print(f"\nagent> {response.message}")
        print(f"stage: {response.state.stage}")
        print("tools:")
        _print_trace(response.trace)
        _print_checks(verifier)
        print()

    _print_checks(verifier)
    if verifier.complete:
        print("Phase 1 verification: PASS")
        return 0
    print("Phase 1 verification: INCOMPLETE")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
