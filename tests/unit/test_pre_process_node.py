from framework.schemas.agent_status import AgentStatus
from src.nodes.pre_process_node import PreProcessNode


def _base_state(**overrides):
    state = {
        "user_input": "what can I cook with this shrimp meal kit?",
        "input_context": {"declared_allergens": ["shellfish"]},
        "correlation_id": "corr-1",
        "caller_trust_level": "ANONYMOUS",
        "execution_time": {},
    }
    state.update(overrides)
    return state


class TestPreProcessNode:
    def test_success_builds_validated_input_json(self):
        node = PreProcessNode()
        result = node.execute(_base_state())

        assert result["status"] == AgentStatus.SUCCESS
        assert result["declared_allergens"] == ["shellfish"]
        assert result["validated_query"] == "what can I cook with this shrimp meal kit?"
        assert "shrimp" in result["validated_input"]
        assert "shellfish" in result["validated_input"]

    def test_text_declared_allergen_parsed_without_input_context(self):
        node = PreProcessNode()
        result = node.execute(
            _base_state(user_input="Plan 3 dinners that are high in protein and avoid shellfish", input_context={})
        )

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["declared_allergens"] == ["shellfish"]
        assert '"shellfish"' in result["validated_input"]

    def test_text_and_context_allergens_merged_and_deduped(self):
        node = PreProcessNode()
        result = node.execute(
            _base_state(
                user_input="dairy-free dinners please, no shrimp",
                input_context={"declared_allergens": ["Shellfish", "egg"]},
            )
        )

        assert result["declared_allergens"] == ["shellfish", "egg", "milk"]

    def test_no_declaration_means_no_allergens(self):
        node = PreProcessNode()
        result = node.execute(_base_state(user_input="Plan 3 dinners with salmon", input_context={}))

        assert result["declared_allergens"] == []

    def test_error_on_empty_user_input(self):
        node = PreProcessNode()
        result = node.execute(_base_state(user_input=""))

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
