import json

from car_agent.conversation_context import ConversationTurn, build_prompt_context
from car_agent.models import ConversationState, ShopperPreferences
from car_agent.tools import SalesTools


def test_prompt_context_keeps_recent_window_and_summarizes_older_turns() -> None:
    history = [
        ConversationTurn(
            user_message=f"Earlier shopper question {index}",
            assistant_message=f"Earlier advisor answer {index}",
        )
        for index in range(6)
    ]
    context = build_prompt_context(history, ConversationState("context-window"), SalesTools().inventory)

    assert len(context.recent_turns) == 4
    assert context.recent_turns[0]["user"] == "Earlier shopper question 2"
    assert "Turn 1" in context.earlier_summary
    assert "Earlier shopper question 0" in context.earlier_summary
    assert "Earlier shopper question 2" not in context.earlier_summary


def test_prompt_context_includes_active_vehicle_and_latest_safe_grounding() -> None:
    history = [
        ConversationTurn(
            user_message="Find me a weekend roadster.",
            assistant_message="I found a Honda S2000.",
            tool_calls=[
                {
                    "name": "list_inventory",
                    "arguments": {"filters": {"intended_use": "weekend"}},
                    "result": {"vehicles": [{"id": "honda-s2000-2004"}]},
                }
            ],
        )
    ]
    state = ConversationState(
        "context-grounding",
        preferences=ShopperPreferences(selected_vehicle_id="honda-s2000-2004"),
        last_vehicle_ids=["honda-s2000-2004"],
    )

    context = build_prompt_context(history, state, SalesTools().inventory)

    assert context.active_vehicle is not None
    assert context.active_vehicle["id"] == "honda-s2000-2004"
    assert context.latest_grounding is not None
    assert context.latest_grounding["name"] == "list_inventory"


def test_prompt_inputs_do_not_forward_schedule_contact_data() -> None:
    history = [
        ConversationTurn(
            user_message="Schedule it for me.",
            assistant_message="Your test-drive request is in.",
            tool_calls=[
                {
                    "name": "create_test_drive",
                    "arguments": {"name": "Alex Rivera", "email": "alex@example.com"},
                    "result": {"request_id": "td-0001"},
                },
                {
                    "name": "get_vehicle_facts",
                    "arguments": {"vehicle_id": "honda-s2000-2004"},
                    "result": {"facts": [{"fact": "Inspect the soft top."}]},
                },
            ],
        )
    ]

    prompt_text = json.dumps(
        build_prompt_context(
            history,
            ConversationState("context-safe"),
            SalesTools().inventory,
        ).as_prompt_inputs()
    )

    assert "alex@example.com" not in prompt_text
    assert "Alex Rivera" not in prompt_text
    assert "get_vehicle_facts" in prompt_text
