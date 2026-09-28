from framework.schemas.agent_status import AgentStatus
from src.nodes.allergen_hard_filter_node import AllergenHardFilterNode


class TestAllergenHardFilterNode:
    def test_success_no_conflicts(self):
        node = AllergenHardFilterNode()
        state = {
            "draft_plan": {"ingredients": [{"name": "tofu", "allergens": []}]},
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        assert result["allergen_warnings"] == []
        assert result["final_plan"]["warnings"] == []

    def test_backstop_removes_conflicting_ingredient_and_warns(self):
        node = AllergenHardFilterNode()
        state = {
            "draft_plan": {
                "ingredients": [{"name": "shrimp", "allergens": ["shellfish"]}, {"name": "tofu", "allergens": []}],
                "steps": ["Prepare shrimp", "Prepare tofu"],
            },
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS.value
        assert [i["name"] for i in result["final_plan"]["ingredients"]] == ["tofu"]
        assert result["final_plan"]["steps"] == ["Prepare tofu"]
        assert len(result["allergen_warnings"]) == 1
        assert "shrimp" in result["allergen_warnings"][0]
        assert "shellfish" in result["allergen_warnings"][0]

    def test_warns_for_ingredient_excluded_upstream(self):
        node = AllergenHardFilterNode()
        state = {
            "draft_plan": {
                "ingredients": [{"name": "tofu", "allergens": []}],
                "excluded": [{"name": "shrimp", "allergens": ["shellfish"]}],
            },
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["final_plan"]["ingredients"] == [{"name": "tofu", "allergens": []}]
        assert result["allergen_warnings"] == [
            "shrimp excluded from the plan: contains declared allergen(s): shellfish"
        ]

    def test_error_when_only_conflicting_ingredients(self):
        node = AllergenHardFilterNode()
        state = {
            "draft_plan": {"ingredients": [{"name": "shrimp", "allergens": ["shellfish"]}]},
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.ERROR.value
        assert "final_plan" not in result

    def test_error_when_warning_would_be_suppressed(self):
        """Life-safety gate: if warning construction drops a real conflict, fail closed."""

        class _BrokenNode(AllergenHardFilterNode):
            def _build_warnings(self, conflicts):
                return []  # simulate a formatting bug that drops every warning

        node = _BrokenNode()
        state = {
            "draft_plan": {"ingredients": [{"name": "shrimp", "allergens": ["shellfish"]}]},
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
        assert "suppressed" in result["error_log"][0]
