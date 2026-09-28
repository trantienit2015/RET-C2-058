from framework.schemas.agent_status import AgentStatus
from src.nodes.post_process_node import PostProcessNode


class TestPostProcessNode:
    def test_formats_final_plan(self):
        node = PostProcessNode()
        state = {
            "final_plan": {"ingredients": [{"name": "shrimp"}], "warnings": []},
            "allergen_warnings": [],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        assert result["formatted_output"]["plan"]["ingredients"][0]["name"] == "shrimp"
        assert result["formatted_output"]["allergen_warning_count"] == 0

    def test_reports_allergen_warning_count(self):
        node = PostProcessNode()
        state = {
            "final_plan": {"ingredients": []},
            "allergen_warnings": ["shrimp contains declared allergen(s): shellfish"],
            "correlation_id": "corr-1",
        }
        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        assert result["formatted_output"]["allergen_warning_count"] == 1
