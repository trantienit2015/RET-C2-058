from src.graph.graph import MealKitPlanningGraphNode


class TestMealKitPlanningGraphNode:
    def test_extract_input_prefers_validated_input(self):
        node = MealKitPlanningGraphNode()
        state = {
            "validated_input": '{"query": "x"}',
            "user_input": "raw",
            "declared_allergens": ["shellfish"],
            "correlation_id": "corr-1",
        }
        assert node.extract_input(state) == '{"query": "x"}'

    def test_merge_output_maps_only_changed_keys(self):
        node = MealKitPlanningGraphNode()
        state = {"correlation_id": "corr-1"}
        sub_result = {
            "query_intent": "planning",
            "retrieved_candidates": [{"name": "tofu"}],
            "draft_plan": {"ingredients": []},
            "allergen_warnings": [],
            "final_plan": {"ingredients": []},
            "status": "success",
        }
        delta = node.merge_output(state, sub_result)

        assert delta["query_intent"] == "planning"
        assert delta["final_plan"] == {"ingredients": []}
        assert delta["status"] == "success"

    def test_parent_config_forwards_dependencies(self):
        node = MealKitPlanningGraphNode(top_k=7, llm="fake-llm", vector_store="fake-store")
        config = node._parent_config()

        assert config == {"top_k": 7, "llm": "fake-llm", "vector_store": "fake-store"}
