"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PostProcessNode(FunctionNode):
    """Format the final meal-kit plan merged back from the inner subgraph."""

    # S-1: outer node — matches agent.yaml required_trust_level (ANONYMOUS).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        final_plan = state.get("final_plan", {})
        allergen_warnings = state.get("allergen_warnings", [])

        formatted_output = {
            "plan": final_plan,
            "allergen_warning_count": len(allergen_warnings),
        }

        emit_trace_event(
            "meal_kit_plan_formatted",
            {
                "correlation_id": state.get("correlation_id"),
                "allergen_warning_count": len(allergen_warnings),
            },
            state,
        )

        return {
            "formatted_output": formatted_output,
            "result": final_plan,
            "status": AgentStatus.SUCCESS.value,
        }
