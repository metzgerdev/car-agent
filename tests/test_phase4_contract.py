import json
import re
import subprocess
import sys

from fastapi.testclient import TestClient

from car_agent.app import create_app
from car_agent.crewai_agent import CrewAISalesAgent
from car_agent.modality import VoiceConversationAdapter, TextConversationAdapter
from car_agent.models import AgentResponse, ConversationState, ToolCall


def _offline_client() -> tuple[TestClient, CrewAISalesAgent]:
    sales_agent = CrewAISalesAgent(use_live_model=False)
    return TestClient(create_app(sales_agent)), sales_agent


def _recommend(agent: CrewAISalesAgent, conversation_id: str = "phase4-test") -> None:
    agent.respond(conversation_id, "I want a weekend convertible under $40k with spirited driving.")


def test_p4_t1_api_contract_and_validation() -> None:
    client, _ = _offline_client()

    health = client.get("/health")
    chat = client.post(
        "/chat",
        json={
            "conversation_id": "api-contract",
            "message": "I want a weekend coupe under $40k with spirited driving.",
        },
    )
    malformed = client.post("/chat", json={"conversation_id": "", "message": "hello"})

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert chat.status_code == 200
    assert {"message", "state", "trace"} <= chat.json().keys()
    assert chat.json()["state"]["stage"] == "recommending"
    assert malformed.status_code == 422


def test_p4_t7_browser_demo_shell_and_assets_are_served() -> None:
    client, _ = _offline_client()

    page = client.get("/")
    asset_paths = re.findall(r'(?:src|href)="(/static/assets/[^"]+)"', page.text)
    assets = [client.get(path) for path in asset_paths]

    assert page.status_code == 200
    assert "Classic Car Advisor" in page.text
    assert '<div id="root"></div>' in page.text
    assert asset_paths
    assert all(asset.status_code == 200 for asset in assets)
    assert any("text/css" in asset.headers.get("content-type", "") for asset in assets)
    assert any("javascript" in asset.headers.get("content-type", "") for asset in assets)
    css_assets = [asset.text for asset in assets if "text/css" in asset.headers.get("content-type", "")]
    javascript_assets = [asset.text for asset in assets if "javascript" in asset.headers.get("content-type", "")]
    assert any("--chat-bg" in css for css in css_assets)
    assert any("color-scheme:dark" in css.replace(" ", "") for css in css_assets)
    assert any("cursor:not-allowed" in css.replace(" ", "") for css in css_assets)
    assert all(".aui-styled-send:disabled{cursor:wait" not in css.replace(" ", "") for css in css_assets)
    assert any("Tool Trace" in javascript for javascript in javascript_assets)
    assert all("Guide the shopper" not in javascript for javascript in javascript_assets)
    assert all("Shopper profile" not in javascript for javascript in javascript_assets)


def test_p4_t10_chat_can_stream_trace_progress_over_sse() -> None:
    client, _ = _offline_client()

    with client.stream(
        "POST",
        "/chat",
        headers={"Accept": "text/event-stream"},
        json={
            "conversation_id": "streaming-trace",
            "message": "I want a weekend coupe under $40k with spirited driving.",
        },
    ) as response:
        lines = list(response.iter_lines())

    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data_lines.append(line.removeprefix("data: "))
        elif not line and event_name:
            events.append((event_name, json.loads("\n".join(data_lines))))
            event_name = None
            data_lines = []

    trace_events = [payload for name, payload in events if name == "trace"]
    completed = [payload for payload in trace_events if payload["status"] == "complete"]
    response_events = [payload for name, payload in events if name == "response"]

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert trace_events
    assert trace_events[0]["status"] == "running"
    assert trace_events[0]["name"] == "search_inventory"
    assert len(completed) == 4
    assert all(payload["call"]["name"] for payload in completed)
    assert [payload["call"]["name"] for payload in completed] == [
        "search_inventory",
        "get_vehicle",
        "get_vehicle",
        "retrieve_vehicle_facts",
    ]
    assert len(response_events) == 1
    assert len(response_events[0]["trace"]) == 4
    assert events[-1][0] == "done"


def test_p4_t11_chat_streams_llm_response_deltas_before_final_response(monkeypatch) -> None:
    agent = CrewAISalesAgent(use_live_model=True)

    def respond(
        conversation_id: str,
        user_message: str,
        *,
        trace_observer=None,
        response_observer=None,
    ) -> AgentResponse:
        if response_observer:
            response_observer("The 2004 Honda ")
            response_observer("S2000 is ready for a closer look.")
        return AgentResponse(
            "The 2004 Honda S2000 is ready for a closer look.",
            ConversationState(conversation_id, stage="recommending"),
            [],
        )

    monkeypatch.setattr(agent, "respond", respond)
    client = TestClient(create_app(agent))

    with client.stream(
        "POST",
        "/chat",
        headers={"Accept": "text/event-stream"},
        json={
            "conversation_id": "streaming-answer",
            "message": "Tell me more about the S2000.",
        },
    ) as response:
        lines = list(response.iter_lines())

    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data_lines.append(line.removeprefix("data: "))
        elif not line and event_name:
            events.append((event_name, json.loads("\n".join(data_lines))))
            event_name = None
            data_lines = []

    deltas = [payload["delta"] for name, payload in events if name == "response_delta"]
    response_index = next(index for index, (name, _) in enumerate(events) if name == "response")

    assert response.status_code == 200
    assert deltas == ["The 2004 Honda ", "S2000 is ready for a closer look."]
    assert [name for name, _ in events[:response_index]] == [
        "response_delta",
        "response_delta",
    ]
    assert events[response_index][1]["message"] == "".join(deltas)
    assert events[-1][0] == "done"


def test_p4_t8_magazine_reviews_are_typed_and_matched_to_inventory() -> None:
    client, _ = _offline_client()

    response = client.get("/vehicles/honda-s2000-2004/reviews")
    recommendation = client.post(
        "/chat",
        json={
            "conversation_id": "review-recommendation",
            "message": "I want a weekend coupe under $40k with spirited driving.",
        },
    )
    missing = client.get("/vehicles/unknown-vehicle/reviews")

    assert response.status_code == 200
    payload = response.json()
    assert payload["vehicle_name"] == "2004 Honda S2000"
    assert len(payload["reviews"]) == 2
    assert {review["outlet"] for review in payload["reviews"]} == {
        "Car and Driver",
        "MotorTrend",
    }
    assert all(review["url"].startswith("https://") for review in payload["reviews"])
    assert all(review["summary"] for review in payload["reviews"])
    recommendation_payload = recommendation.json()
    assert recommendation.status_code == 200
    assert recommendation_payload["reviews"]
    assert any(
        group["vehicle_name"] == "2008 BMW Z4 M Coupe"
        for group in recommendation_payload["reviews"]
    )
    assert missing.status_code == 404

    agent = CrewAISalesAgent(use_live_model=False)
    vehicle = agent.tools.inventory.get("bmw-z4-m-2008")
    assert vehicle is not None

    def respond_with_tool_suggestion(conversation_id: str, user_message: str) -> AgentResponse:
        return AgentResponse(
            "The BMW M3 is unavailable, but consider the BMW Z4 M Coupe.",
            ConversationState(conversation_id),
            [
                ToolCall(
                    name="search_inventory",
                    arguments={"filters": {"query": "BMW M3"}},
                    result={"count": 1, "vehicles": [vehicle.to_dict()]},
                )
            ],
        )

    agent.respond = respond_with_tool_suggestion  # type: ignore[method-assign]
    trace_client = TestClient(create_app(agent))
    trace_payload = trace_client.post(
        "/chat",
        json={"conversation_id": "trace-review", "message": "Find another BMW."},
    ).json()

    assert [group["vehicle_name"] for group in trace_payload["reviews"]] == [
        "2008 BMW Z4 M Coupe"
    ]


def test_p4_t2_invalid_schedule_never_creates_a_request() -> None:
    client, agent = _offline_client()
    _recommend(agent, "invalid-schedule")

    invalid_email = client.post(
        "/chat",
        json={
            "conversation_id": "invalid-schedule",
            "message": "Schedule a test drive for the Honda S2000. My name is Alex Rivera and my email is invalid.",
        },
    )
    unknown_vehicle = client.post(
        "/chat",
        json={
            "conversation_id": "unknown-schedule",
            "message": "Please schedule a test drive for the imaginary 2030 Roadster.",
        },
    )

    assert invalid_email.status_code == 200
    assert invalid_email.json()["state"]["stage"] == "scheduling"
    assert not any(call["name"] == "schedule_test_drive" for call in invalid_email.json()["trace"])
    assert unknown_vehicle.status_code == 200
    assert not any(call["name"] == "schedule_test_drive" for call in unknown_vehicle.json()["trace"])
    assert len(agent.tools.scheduler.requests) == 0


def test_p4_t3_identical_booking_is_idempotent() -> None:
    agent = CrewAISalesAgent(use_live_model=False)
    _recommend(agent, "duplicate-booking")
    message = (
        "Schedule a test drive for the Honda S2000. My name is Alex Rivera, "
        "my email is alex@example.com, and Saturday at 10am works."
    )

    first = agent.respond("duplicate-booking", message)
    second = agent.respond("duplicate-booking", message)

    assert first.state.stage == "scheduled"
    assert second.state.stage == "scheduled"
    assert len(agent.tools.scheduler.requests) == 1
    assert first.trace[-1].result["request"]["request_id"] == "td-0001"
    assert second.trace[-1].result["request"]["request_id"] == "td-0001"
    assert second.trace[-1].result["duplicate"] is True


def test_p4_t4_public_response_redacts_contact_values() -> None:
    agent = CrewAISalesAgent(use_live_model=False)
    _recommend(agent, "redaction")
    response = agent.respond(
        "redaction",
        "Schedule a test drive for the Honda S2000. My name is Alex Rivera, "
        "my email is alex@example.com, and Saturday at 10am works.",
    )

    public_payload = response.to_dict()
    serialized = json.dumps(public_payload)

    assert "Alex Rivera" not in serialized
    assert "alex@example.com" not in serialized
    assert public_payload["state"]["preferences"]["name"] == "[REDACTED]"
    assert public_payload["state"]["preferences"]["email"] == "[REDACTED]"
    schedule_trace = public_payload["trace"][-1]
    assert schedule_trace["arguments"]["name"] == "[REDACTED]"
    assert schedule_trace["arguments"]["email"] == "[REDACTED]"
    assert "alex@example.com" not in response.message


def test_p4_t5_text_and_voice_share_one_domain_command() -> None:
    text = TextConversationAdapter.to_command(
        "modality",
        "I want a weekend car under $40k with spirited driving.",
    )
    voice = VoiceConversationAdapter.to_command(
        "modality",
        "Um, I want a weekend car under $40k with spirited driving.",
    )

    assert text == voice
    assert text.intent == "recommend"


def test_p4_t6_clean_checkout_demo_runs_to_completion() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "car_agent.demo_cli"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Demo result: PASS" in result.stdout
