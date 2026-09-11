"""Scenario evaluation for the deterministic router."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .agent import DeterministicRouter


class Phase3Scenario(BaseModel):
    """One scripted conversation and its expected result."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    turns: list[str] = Field(min_length=1)
    expected_stage: str
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    forbidden_final_tools: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)
    budget_max: int | None = Field(default=None, gt=0)
    max_questions_per_turn: int = Field(default=2, ge=0)


class ScenarioResult(BaseModel):
    """Result of one scenario evaluation."""

    scenario_id: str
    passed: bool
    final_stage: str
    final_message: str
    tool_names: list[str]
    failures: list[str] = Field(default_factory=list)
    budget_violations: list[str] = Field(default_factory=list)


class Phase3EvaluationReport(BaseModel):
    """Aggregate scenario evaluation result."""

    results: list[ScenarioResult]
    passed_count: int
    budget_violation_count: int

    @property
    def total_count(self) -> int:
        return len(self.results)


def run_phase3_evaluation(
    scenarios: list[Phase3Scenario] | None = None,
) -> Phase3EvaluationReport:
    """Run scripted scenarios against offline agent sessions."""

    cases = scenarios or phase3_scenarios()
    results: list[ScenarioResult] = []
    for scenario in cases:
        agent = DeterministicRouter()
        responses = [
            agent.respond(scenario.scenario_id, turn)
            for turn in scenario.turns
        ]
        final_response = responses[-1]
        tool_names = [call.name for response in responses for call in response.trace]
        final_tool_names = [call.name for call in final_response.trace]
        failures: list[str] = []
        budget_violations: list[str] = []

        if final_response.state.stage != scenario.expected_stage:
            failures.append(
                f"expected stage {scenario.expected_stage!r}, got {final_response.state.stage!r}"
            )
        for tool in scenario.required_tools:
            if tool not in tool_names:
                failures.append(f"required tool {tool!r} was not called")
        for tool in scenario.forbidden_tools:
            if tool in tool_names:
                failures.append(f"forbidden tool {tool!r} was called")
        for tool in scenario.forbidden_final_tools:
            if tool in final_tool_names:
                failures.append(f"forbidden final-turn tool {tool!r} was called")
        final_lower = final_response.message.lower()
        for phrase in scenario.required_phrases:
            if phrase.lower() not in final_lower:
                failures.append(f"final response did not contain {phrase!r}")
        for turn, response in zip(scenario.turns, responses):
            question_count = response.message.count("?")
            if question_count > scenario.max_questions_per_turn:
                failures.append(
                    f"turn {turn!r} asked {question_count} questions; maximum is {scenario.max_questions_per_turn}"
                )
            for call in response.trace:
                if call.name != "list_inventory" or scenario.budget_max is None:
                    continue
                for vehicle in call.result.get("vehicles", []):
                    price = vehicle.get("price")
                    if isinstance(price, int) and price > scenario.budget_max:
                        budget_violations.append(
                            f"{vehicle.get('id', 'unknown')} priced at {price} exceeds {scenario.budget_max}"
                        )
        if budget_violations:
            failures.append("hard budget constraint was violated")

        results.append(
            ScenarioResult(
                scenario_id=scenario.scenario_id,
                passed=not failures,
                final_stage=final_response.state.stage,
                final_message=final_response.message,
                tool_names=tool_names,
                failures=failures,
                budget_violations=budget_violations,
            )
        )

    return Phase3EvaluationReport(
        results=results,
        passed_count=sum(result.passed for result in results),
        budget_violation_count=sum(len(result.budget_violations) for result in results),
    )


def phase3_scenarios() -> list[Phase3Scenario]:
    """Return the scenario evaluation set."""

    return [
        Phase3Scenario(
            scenario_id="p3-t1-budget-only",
            turns=["I have $45k to spend."],
            expected_stage="qualifying",
            forbidden_tools=["list_inventory"],
            required_phrases=["use"],
            budget_max=45_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t1-incomplete-preferences",
            turns=["I want a car under $40k.", "It will be a weekend car."],
            expected_stage="qualifying",
            forbidden_tools=["list_inventory"],
            required_phrases=["driving"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t1-progressive-qualification",
            turns=[
                "I want something under $45k.",
                "It will be a weekend car for spirited driving, preferably a coupe.",
            ],
            expected_stage="recommending",
            required_tools=["list_inventory", "get_vehicle_facts"],
            required_phrases=["I found"],
            budget_max=45_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t1-state-persists",
            turns=[
                "My maximum is $40k.",
                "I will use it on weekends.",
                "I prefer spirited driving in a coupe.",
            ],
            expected_stage="recommending",
            required_tools=["list_inventory"],
            required_phrases=["I found"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t2-hard-budget",
            turns=["Weekend sports car, spirited driving, coupe, under $40k."],
            expected_stage="recommending",
            required_tools=["list_inventory"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t2-convertible-ranking",
            turns=["I want a weekend convertible under $40k with spirited driving."],
            expected_stage="recommending",
            required_tools=["list_inventory"],
            required_phrases=["Honda S2000"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t2-coupe-ranking",
            turns=["I want a weekend coupe under $40k with spirited driving."],
            expected_stage="recommending",
            required_tools=["list_inventory"],
            required_phrases=["Mazda RX-7"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t2-compare-last-matches",
            turns=[
                "I have $80k for a daily car and like spirited driving.",
                "Can you compare those two?",
            ],
            expected_stage="recommending",
            required_tools=["get_vehicle_comparison"],
            required_phrases=["short version"],
            budget_max=80_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t2-compare-named-models",
            turns=["Compare the Honda S2000 and Porsche 911 Carrera."],
            expected_stage="recommending",
            required_tools=["get_vehicle_comparison"],
            required_phrases=["Honda S2000", "Porsche 911 Carrera"],
            budget_max=80_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t3-grounded-facts",
            turns=[
                "I have $40k for a weekend car and want analog driving.",
                "What should I inspect on the Honda S2000?",
            ],
            expected_stage="recommending",
            required_tools=["get_vehicle_facts"],
            required_phrases=["soft top"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t3-facts-from-context",
            turns=[
                "I want a weekend coupe under $40k with spirited driving.",
                "What ownership notes do you have?",
            ],
            expected_stage="recommending",
            required_tools=["get_vehicle_facts"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t3-ambiguous-make",
            turns=["I like Porsche."],
            expected_stage="qualifying",
            forbidden_tools=["list_inventory", "get_vehicle"],
            required_phrases=["specific model"],
        ),
        Phase3Scenario(
            scenario_id="p3-t3-ambiguous-make-with-budget",
            turns=["I like Porsche and can spend up to $80k."],
            expected_stage="qualifying",
            forbidden_tools=["list_inventory"],
            required_phrases=["911 Carrera"],
            budget_max=80_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t4-unsupported-named-spec",
            turns=[
                "I want a weekend coupe under $50k with spirited driving.",
                "Does the Porsche 911 Carrera have adaptive cruise?",
            ],
            expected_stage="recommending",
            forbidden_final_tools=["get_vehicle_facts"],
            required_phrases=["won’t guess"],
            budget_max=50_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t4-unsupported-context-spec",
            turns=[
                "I want a weekend coupe under $40k with spirited driving.",
                "Does it have four-wheel steering?",
            ],
            expected_stage="recommending",
            forbidden_final_tools=["get_vehicle_facts"],
            required_phrases=["official source"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t5-maintenance-objection",
            turns=[
                "I want a weekend roadster under $40k with spirited driving.",
                "I’m worried about maintenance on the Honda S2000.",
            ],
            expected_stage="recommending",
            required_tools=["get_vehicle_facts"],
            required_phrases=["trade-off", "soft top"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t5-price-objection",
            turns=[
                "I want a weekend coupe under $40k with spirited driving.",
                "The Mazda RX-7 price feels too expensive.",
            ],
            expected_stage="recommending",
            required_tools=["get_vehicle_facts"],
            required_phrases=["trade-off", "asking price"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t5-schedule-needs-vehicle",
            turns=["Please schedule a test drive."],
            expected_stage="qualifying",
            forbidden_tools=["create_test_drive"],
            required_phrases=["specific car"],
        ),
        Phase3Scenario(
            scenario_id="p3-t5-schedule-collects-contact",
            turns=[
                "I want a weekend convertible under $40k with spirited driving.",
                "Please schedule a test drive for the Honda S2000.",
            ],
            expected_stage="scheduling",
            forbidden_tools=["create_test_drive"],
            required_phrases=["name"],
            budget_max=40_000,
        ),
        Phase3Scenario(
            scenario_id="p3-t6-valid-conversion",
            turns=[
                "I want a weekend convertible under $40k with spirited driving.",
                "Schedule a test drive for the Honda S2000. My name is Alex Rivera, my email is alex@example.com, and Saturday at 10am works.",
            ],
            expected_stage="scheduled",
            required_tools=["create_test_drive"],
            required_phrases=["td-0001"],
            budget_max=40_000,
        ),
    ]
