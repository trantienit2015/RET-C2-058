"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

# Node contract:
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return status as AgentStatus.<X>.value (the string), never the bare enum
#  - Read input_context via state.get("input_context", {}) — read-only [C1]
#  - Never import from mediator/, api/, or other agents

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.allergen_declaration import merge_declared_allergens


class PreProcessNode(FunctionNode):
    """Validate the meal-kit query + declared allergens, build validated_input.

    declared_allergens is the union of input_context["declared_allergens"]
    and the avoidances stated in the request text ("avoid shellfish",
    "nut-free"), normalised to canonical allergen names. It is session-scoped
    input ONLY — never persisted beyond this invocation — and this node never
    logs allergen names (only a count) via emit_trace_event.
    """

    # S-1: outer node — matches agent.yaml required_trust_level (ANONYMOUS,
    # public shopper-facing read).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        input_context = state.get("input_context", {}) or {}  # read-only [C1]
        context_allergens = input_context.get("declared_allergens", []) if isinstance(input_context, dict) else []

        if not user_input or not user_input.strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PreProcessNode: user_input is empty or missing"],
            }

        query = user_input.strip()
        declared_allergens = merge_declared_allergens(context_allergens, query)
        payload = {"query": query, "declared_allergens": list(declared_allergens)}

        emit_trace_event(
            "meal_kit_query_validated",
            {
                "correlation_id": state.get("correlation_id"),
                "allergen_count": len(declared_allergens),
            },
            state,
        )

        return {
            "validated_query": query,
            "declared_allergens": list(declared_allergens),
            "validated_input": json.dumps(payload, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
