"""Bounded conversation context for live prompts."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .models import ConversationState
from .repositories import InventoryRepository


RECENT_TURN_LIMIT = 4
SUMMARY_CHAR_LIMIT = 1_600
MESSAGE_CHAR_LIMIT = 900
GROUNDING_CHAR_LIMIT = 3_500
GROUNDING_TOOLS = {
    "list_inventory",
    "lookup_vehicle_exact",
    "get_vehicle",
    "get_vehicle_facts",
    "get_service_history",
    "get_magazine_reviews",
    "get_vehicle_comparison",
}


class ConversationTurn(BaseModel):
    """One complete user/assistant exchange retained by the backend."""

    user_message: str
    assistant_message: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ConversationPromptContext(BaseModel):
    """The bounded, grounded subset of conversation memory sent to the LLM."""

    recent_turns: list[dict[str, Any]] = Field(default_factory=list)
    earlier_summary: str = ""
    active_vehicle: dict[str, Any] | None = None
    latest_grounding: dict[str, Any] | None = None

    def as_prompt_inputs(self) -> dict[str, str]:
        """Serialize each context section for explicit CrewAI task inputs."""

        return {
            "recent_history": _json_or_none(self.recent_turns),
            "conversation_summary": self.earlier_summary or "None.",
            "active_vehicle": _json_or_none(self.active_vehicle),
            "latest_grounding": _json_or_none(self.latest_grounding),
        }


def build_prompt_context(
    history: list[ConversationTurn],
    state: ConversationState,
    inventory: InventoryRepository,
) -> ConversationPromptContext:
    """Build prompt context from recent turns and state."""

    recent_start = max(0, len(history) - RECENT_TURN_LIMIT)
    recent_turns = [
        {
            "user": _clip(turn.user_message, MESSAGE_CHAR_LIMIT),
            "assistant": _clip(turn.assistant_message, MESSAGE_CHAR_LIMIT),
            "tools": [call.get("name") for call in turn.tool_calls if call.get("name")],
        }
        for turn in history[recent_start:]
    ]
    earlier_summary = _summarize_earlier_turns(history[:recent_start])
    active_id = state.preferences.selected_vehicle_id or (state.last_vehicle_ids[0] if state.last_vehicle_ids else None)
    active_vehicle = (
        inventory.get(active_id).to_dict(include_service_history=False)
        if active_id and inventory.get(active_id)
        else None
    )
    latest_grounding = _latest_grounding(history)
    return ConversationPromptContext(
        recent_turns=recent_turns,
        earlier_summary=earlier_summary,
        active_vehicle=active_vehicle,
        latest_grounding=latest_grounding,
    )


def _summarize_earlier_turns(history: list[ConversationTurn]) -> str:
    if not history:
        return ""
    lines = []
    for index, turn in enumerate(history, start=1):
        tools = ", ".join(call["name"] for call in turn.tool_calls if call.get("name")) or "none"
        lines.append(
            f"Turn {index}: shopper asked {_clip(turn.user_message, 180)!r}; "
            f"advisor responded {_clip(turn.assistant_message, 260)!r}; tools: {tools}."
        )
    return _clip(" ".join(lines), SUMMARY_CHAR_LIMIT)


def _latest_grounding(history: list[ConversationTurn]) -> dict[str, Any] | None:
    for turn in reversed(history):
        for call in reversed(turn.tool_calls):
            if call.get("name") not in GROUNDING_TOOLS:
                continue
            safe_call = {
                "name": call.get("name"),
                "arguments": call.get("arguments", {}),
                "result": call.get("result", {}),
            }
            return json.loads(_clip(json.dumps(safe_call, ensure_ascii=False), GROUNDING_CHAR_LIMIT)) if _fits_json(safe_call) else {
                "name": safe_call["name"],
                "arguments": safe_call["arguments"],
                "result": _clip(json.dumps(safe_call["result"], ensure_ascii=False), GROUNDING_CHAR_LIMIT),
            }
    return None


def _json_or_none(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False) if value else "None."


def _fits_json(value: Any) -> bool:
    return len(json.dumps(value, ensure_ascii=False)) <= GROUNDING_CHAR_LIMIT


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"
