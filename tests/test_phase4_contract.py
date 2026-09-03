import json
import subprocess
import sys

from fastapi.testclient import TestClient

from car_agent.app import create_app
from car_agent.crewai_agent import CrewAISalesAgent
from car_agent.modality import VoiceConversationAdapter, TextConversationAdapter


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
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "Classic Car Advisor" in page.text
    assert "data-prompt" in page.text
    assert "Shopper profile" in page.text
    assert "Grounding evidence" in page.text
    assert stylesheet.status_code == 200
    assert "conversation-card" in stylesheet.text
    assert script.status_code == 200
    assert 'fetch("/chat"' in script.text


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
