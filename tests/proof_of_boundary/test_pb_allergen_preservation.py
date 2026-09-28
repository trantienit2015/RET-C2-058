# PB-life-safety: Allergen warning preservation.
#
# Life-safety requirement (RET-C2-058): AllergenHardFilterNode is a
# non-suppressible S-3 preservation-variant gate. An allergen warning that
# should appear in the final plan must NEVER be silently absent from the
# node's output — if warning construction would drop it, the node MUST fail
# closed (AgentStatus.ERROR), not return a plan missing the warning.

from framework.schemas.agent_status import AgentStatus
from src.nodes.allergen_hard_filter_node import AllergenHardFilterNode


class TestAllergenWarningPreservation:
    def test_warning_present_in_input_is_never_absent_from_output(self):
        node = AllergenHardFilterNode()
        state = {
            "draft_plan": {
                "ingredients": [
                    {"name": "shrimp", "allergens": ["shellfish"]},
                    {"name": "peanut sauce", "allergens": ["peanut"]},
                    {"name": "rice", "allergens": []},
                ]
            },
            "declared_allergens": ["shellfish", "peanut"],
            "correlation_id": "corr-pb-1",
        }

        result = node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        warnings_text = " | ".join(result["allergen_warnings"])
        assert "shrimp" in warnings_text and "shellfish" in warnings_text
        assert "peanut sauce" in warnings_text and "peanut" in warnings_text
        # final_plan is what reaches the caller — the warnings must be present there too.
        assert result["final_plan"]["warnings"] == result["allergen_warnings"]

    def test_node_fails_closed_rather_than_ship_a_plan_missing_a_warning(self):
        """Simulate a bug that would drop a warning — the node must refuse, not ship silently."""

        class _RegressedNode(AllergenHardFilterNode):
            def _build_warnings(self, conflicts):
                # Regression: only builds a warning for the first conflict.
                return super()._build_warnings(conflicts[:1])

        node = _RegressedNode()
        state = {
            "draft_plan": {
                "ingredients": [
                    {"name": "shrimp", "allergens": ["shellfish"]},
                    {"name": "peanut sauce", "allergens": ["peanut"]},
                ]
            },
            "declared_allergens": ["shellfish", "peanut"],
            "correlation_id": "corr-pb-2",
        }

        result = node.execute(state)

        # MUST fail closed — never return a plan silently missing an allergen warning.
        assert result["status"] == AgentStatus.ERROR
        assert "suppressed" in result["error_log"][0]
        assert "final_plan" not in result
