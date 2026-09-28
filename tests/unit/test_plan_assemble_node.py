from framework.schemas.agent_status import AgentStatus
from src.nodes.plan_assemble_node import PlanAssembleNode


class TestPlanAssembleNode:
    def test_success_substitutes_conflicting_ingredient(self):
        node = PlanAssembleNode()
        candidates = [
            {"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}},
            {"name": "tofu", "allergens": [], "nutrition": {"calories": 80}},
        ]
        state = {
            "retrieved_candidates": candidates,
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        names = [ing["name"] for ing in result["draft_plan"]["ingredients"]]
        assert "shrimp" not in names  # substituted away
        assert "tofu" in names
        assert result["draft_plan"]["nutrition"]["calories"] >= 0

    def test_errors_when_no_allergen_safe_candidate_exists(self):
        node = PlanAssembleNode()
        candidates = [{"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}}]
        state = {
            "retrieved_candidates": candidates,
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        # A conflicting ingredient never enters the plan, even without a substitute.
        assert result["status"] == AgentStatus.ERROR.value
        assert "draft_plan" not in result

    def test_conflicting_ingredient_excluded_and_recorded_without_duplicates(self):
        node = PlanAssembleNode()
        candidates = [
            {"name": "chicken", "allergens": [], "nutrition": {"calories": 200}},
            {"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}},
            {"name": "salmon", "allergens": ["fish"], "nutrition": {"calories": 300}},
        ]
        result = node.execute(
            {"retrieved_candidates": candidates, "declared_allergens": ["shellfish"], "correlation_id": "c"}
        )

        assert result["status"] == AgentStatus.SUCCESS.value
        names = [ing["name"] for ing in result["draft_plan"]["ingredients"]]
        assert "shrimp" not in names
        assert len(names) == len(set(names))  # a substitute already in the plan is not added twice
        assert result["draft_plan"]["excluded"] == [{"name": "shrimp", "allergens": ["shellfish"]}]

    def test_no_declaration_keeps_shrimp(self):
        node = PlanAssembleNode()
        candidates = [{"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}}]
        result = node.execute({"retrieved_candidates": candidates, "declared_allergens": [], "correlation_id": "c"})

        assert result["status"] == AgentStatus.SUCCESS.value
        assert [i["name"] for i in result["draft_plan"]["ingredients"]] == ["shrimp"]

    def test_error_on_no_candidates(self):
        node = PlanAssembleNode()
        result = node.execute({"retrieved_candidates": [], "declared_allergens": [], "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
