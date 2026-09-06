import json
import importlib
import re
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from car_agent.app import create_app
from car_agent.crewai_agent import CrewAISalesAgent
from car_agent.modality import VoiceConversationAdapter, TextConversationAdapter
from car_agent.models import AgentResponse, ConversationState, ToolCall


app_module = importlib.import_module("car_agent.app")


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
    deltas = [payload["delta"] for name, payload in events if name == "response_delta"]
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
    assert len(deltas) > 1
    response_index = next(index for index, (name, _) in enumerate(events) if name == "response")
    assert all(name == "response_delta" for name, _ in events[:response_index] if name != "trace")
    assert "".join(deltas) == response_events[0]["message"]
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


def test_p4_t12_trace_history_reducer_preserves_repeated_calls_across_turns() -> None:
    source = Path(__file__).parents[1] / "frontend" / "src" / "main.tsx"
    javascript = ""
    client, _ = _offline_client()
    page = client.get("/")
    asset_paths = re.findall(r'(?:src|href)="(/static/assets/[^"]+)"', page.text)
    for asset_path in asset_paths:
        asset = client.get(asset_path)
        if "javascript" in asset.headers.get("content-type", ""):
            javascript += asset.text

    source_text = source.read_text()
    assert "onStreamStarted" in source_text
    assert "turnTraceCount" in source_text
    assert 'from "./trace-history.js"' in source_text
    assert "mergeTraceHistory(current.trace, current.turnTraceCount, payload.trace)" in source_text
    assert "turnTraceCount" in javascript


def test_p4_t13_browser_shows_thinking_placeholder_during_processing() -> None:
    source = Path(__file__).parents[1] / "frontend" / "src"
    main_text = (source / "main.tsx").read_text()
    thread_text = (source / "components" / "assistant-ui" / "elements" / "thread.tsx").read_text()
    css_text = (source / "styles.css").read_text()

    assert "isProcessing: boolean" in main_text
    assert "onResponseDelta" in main_text
    assert "isProcessing={dashboard.isProcessing}" in main_text
    assert "isProcessing ? <ThinkingPlaceholder /> : null" in thread_text
    assert 'aria-label="Thinking..."' in thread_text
    assert ".aui-thinking-dots" in css_text


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


def test_p4_t15_scribe_token_is_server_minted_without_exposing_api_key(monkeypatch) -> None:
    client, _ = _offline_client()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"token": "single-use-scribe-token"}

    def fake_post(url: str, *, headers: dict[str, str], timeout: float) -> FakeResponse:
        captured.update(url=url, headers=headers, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(app_module.httpx, "post", fake_post)
    response = client.get("/voice/scribe-token")

    assert response.status_code == 200
    assert response.json() == {"token": "single-use-scribe-token"}
    assert captured["url"] == "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"
    assert captured["headers"] == {"xi-api-key": "test-elevenlabs-key"}
    assert "test-elevenlabs-key" not in response.text


def test_p4_t15_voice_endpoints_fail_cleanly_when_unconfigured(monkeypatch) -> None:
    client, _ = _offline_client()
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    token = client.get("/voice/scribe-token")
    speech = client.post("/voice/speak", json={"text": "Hello"})

    assert token.status_code == 503
    assert speech.status_code == 503
    assert "ELEVENLABS_API_KEY" in token.json()["detail"]
    assert "ELEVENLABS_VOICE_ID" in speech.json()["detail"]


def test_p4_t15_voice_speech_returns_audio_stream(monkeypatch) -> None:
    client, _ = _offline_client()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice-id")
    requested: list[str] = []

    def fake_stream(text: str):
        requested.append(text)
        yield b"audio-part-one"
        yield b"audio-part-two"

    monkeypatch.setattr(app_module, "_stream_elevenlabs_tts", fake_stream)
    response = client.post("/voice/speak", json={"text": "  Welcome to the S2000.  "})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.content == b"audio-part-oneaudio-part-two"
    assert requested == ["Welcome to the S2000."]


def test_p4_t15_browser_voice_controls_use_scribe_and_existing_chat_boundary() -> None:
    root = Path(__file__).parents[1]
    thread_source = (root / "frontend" / "src" / "components" / "assistant-ui" / "elements" / "thread.tsx").read_text()
    main_source = (root / "frontend" / "src" / "main.tsx").read_text()
    package = json.loads((root / "frontend" / "package.json").read_text())

    assert "@elevenlabs/react" in package["dependencies"]
    assert 'useScribe' in thread_source
    assert '"/voice/scribe-token"' in thread_source
    assert '"/voice/speak"' in main_source
    assert "body: JSON.stringify({ conversation_id: conversationId, message, modality })" in main_source
