"""HTTP interface for the text-first demo."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .agent import DemoSalesAgent

app = FastAPI(title="Classic Sports Car Sales Agent", version="0.1.0")
agent = DemoSalesAgent()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    return agent.respond(request.conversation_id, request.message).to_dict()
