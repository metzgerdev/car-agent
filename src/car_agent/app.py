"""HTTP interface for the text-first demo."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .crewai_agent import CrewAISalesAgent
from .modality import normalize_command
from .repositories import ReviewRepository
from .review_models import MagazineReview


WEB_ROOT = Path(__file__).parent / "web"


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    modality: Literal["text", "voice"] = "text"

    @field_validator("conversation_id", "message")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ChatResponse(BaseModel):
    message: str
    state: dict[str, Any]
    trace: list[dict[str, Any]]


class ReviewResponse(BaseModel):
    vehicle_id: str
    vehicle_name: str
    reviews: list[MagazineReview]


def create_app(
    sales_agent: CrewAISalesAgent | None = None,
    review_repository: ReviewRepository | None = None,
) -> FastAPI:
    """Create an API app with an injectable agent for offline verification."""

    api = FastAPI(title="Classic Sports Car Sales Agent", version="0.1.0")
    service = sales_agent or CrewAISalesAgent(use_live_model=True)
    reviews = review_repository or ReviewRepository()
    api.state.agent = service
    api.state.review_repository = reviews
    api.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


    @api.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")


    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")


    @api.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        command = normalize_command(request.conversation_id, request.message, request.modality)
        response = service.respond(command.conversation_id, command.message)
        return ChatResponse.model_validate(response.to_dict())


    @api.get("/vehicles/{vehicle_id}/reviews", response_model=ReviewResponse)
    def vehicle_reviews(vehicle_id: str) -> ReviewResponse:
        vehicle = service.tools.inventory.get(vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        return ReviewResponse(
            vehicle_id=vehicle.id,
            vehicle_name=vehicle.name,
            reviews=reviews.retrieve(vehicle),
        )

    return api


app = create_app()
agent: CrewAISalesAgent = app.state.agent
