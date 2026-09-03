import json
import sys

from car_agent.models import AgentResponse, ConversationState


def test_supported_runtime_is_python_312() -> None:
    assert sys.version_info[:2] == (3, 12)


def test_agent_response_contract_is_json_serializable() -> None:
    response = AgentResponse(
        message="hello",
        state=ConversationState("contract"),
        trace=[],
    )

    encoded = json.dumps(response.to_dict())

    assert '"message": "hello"' in encoded
    assert '"conversation_id": "contract"' in encoded
