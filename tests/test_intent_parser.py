from pydantic import BaseModel

from car_agent.intent_parser import IntentEnvelope, LLMIntentParser


class FakeIntentModel:
    def __init__(self) -> None:
        self.messages = None
        self.response_model: type[BaseModel] | None = None

    def call(self, messages, *, response_model):
        self.messages = messages
        self.response_model = response_model
        return {
            "intent": "search_inventory",
            "confidence": 0.93,
            "filters": {"query": "BMW", "intended_use": "weekend"},
        }


def test_llm_intent_parser_requires_and_validates_structured_output() -> None:
    model = FakeIntentModel()
    parser = LLMIntentParser(model)

    result = parser.parse("I’m hunting for a classic Beemer for weekends.", known_makes=["BMW", "Honda"])

    assert isinstance(result, IntentEnvelope)
    assert result.intent == "search_inventory"
    assert result.confidence == 0.93
    assert result.filters.query == "BMW"
    assert result.filters.intended_use == "weekend"
    assert model.response_model is IntentEnvelope
    assert model.messages[1]["content"]
