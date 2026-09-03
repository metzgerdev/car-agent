"""Shared text and voice input boundary for the conversation domain."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ConversationIntent = Literal["recommend", "compare", "facts", "schedule", "unknown"]


class DomainConversationCommand(BaseModel):
    """Normalized command consumed by the text conversation domain."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    intent: ConversationIntent

    @field_validator("conversation_id", "message")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class TextConversationAdapter:
    """Normalize a typed text input into the shared domain command."""

    @staticmethod
    def to_command(conversation_id: str, text: str) -> DomainConversationCommand:
        return _to_command(conversation_id, text)


class VoiceConversationAdapter:
    """Normalize a voice transcript into the same command as text input."""

    @staticmethod
    def to_command(conversation_id: str, transcript: str) -> DomainConversationCommand:
        without_fillers = re.sub(
            r"\b(?:um+|uh+|erm)\b[,.]?\s*",
            "",
            transcript,
            flags=re.IGNORECASE,
        )
        return _to_command(conversation_id, without_fillers)


def normalize_command(
    conversation_id: str,
    message: str,
    modality: Literal["text", "voice"] = "text",
) -> DomainConversationCommand:
    adapter = VoiceConversationAdapter if modality == "voice" else TextConversationAdapter
    return adapter.to_command(conversation_id, message)


def _to_command(conversation_id: str, message: str) -> DomainConversationCommand:
    normalized = re.sub(r"\s+", " ", message).strip()
    lowered = normalized.lower()
    if any(term in lowered for term in ("test drive", "test-drive", "schedule", "book")):
        intent: ConversationIntent = "schedule"
    elif "compar" in lowered or " versus " in f" {lowered} " or re.search(r"\bvs\.?\b", lowered):
        intent = "compare"
    elif any(term in lowered for term in ("ownership", "maintenance", "inspect", "service", "reliable")):
        intent = "facts"
    elif normalized:
        intent = "recommend"
    else:
        intent = "unknown"
    return DomainConversationCommand(
        conversation_id=conversation_id,
        message=normalized,
        intent=intent,
    )
