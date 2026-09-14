import pytest
from pydantic import BaseModel, ValidationError

from car_agent.intent_parser import IntentEnvelope, LLMIntentParser


class FakeIntentModel:
    def __init__(self) -> None:
        self.messages = None
        self.response_model: type[BaseModel] | None = None

    def call(self, messages, *, response_model):
        self.messages = messages
        self.response_model = response_model
        return {
            "intent": "list_inventory",
            "confidence": 0.93,
            "filters": {
                "query": "BMW",
                "budget_max": None,
                "intended_use": "weekend",
                "body_style": None,
                "driving_style": None,
            },
        }


def test_llm_intent_parser_requires_and_validates_structured_output() -> None:
    model = FakeIntentModel()
    parser = LLMIntentParser(model)

    result = parser.parse("I’m hunting for a classic Beemer for weekends.", known_makes=["BMW", "Honda"])

    assert isinstance(result, IntentEnvelope)
    assert result.intent == "list_inventory"
    assert result.confidence == 0.93
    assert result.filters.query == "BMW"
    assert result.filters.intended_use == "weekend"
    assert model.response_model is IntentEnvelope
    assert model.messages[1]["content"]
    assert "Include every filters field" in model.messages[0]["content"]


def test_intent_structured_output_schema_is_strict_and_requires_null_fields() -> None:
    schema = IntentEnvelope.model_json_schema()

    def assert_strict_objects(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
                assert set(value.get("required", [])) == set(value.get("properties", {}))
            for nested in value.values():
                assert_strict_objects(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_strict_objects(nested)

    assert_strict_objects(schema)
    with pytest.raises(ValidationError):
        IntentEnvelope.model_validate(
            {
                "intent": "list_inventory",
                "confidence": 0.9,
                "filters": {"query": "BMW"},
            }
        )
