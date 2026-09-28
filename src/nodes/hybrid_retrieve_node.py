"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph (inner node)"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.meal_kit_kb_service import MealKitKBService


class HybridRetrieveNode(FunctionNode):
    """Hybrid keyword + dense-vector retrieval over the meal-kit KB."""

    # S-1: inner subgraph node — trust authenticated once at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, top_k: int = 5, vector_store: Any = None, kb_service: MealKitKBService | None = None):
        self._top_k = top_k
        self._kb_service = kb_service or MealKitKBService(vector_store=vector_store)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner topology is linear (no conditional routing) — an upstream node
        # error must not be silently overwritten by this node's own SUCCESS.
        if state.get("status") == AgentStatus.ERROR.value:
            return {}

        query = state.get("validated_query", "")
        if not query:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["HybridRetrieveNode: no validated_query to retrieve against"],
            }

        candidates = self._kb_service.hybrid_search(query, top_k=self._top_k)

        emit_trace_event(
            "meal_kit_kb_retrieved",
            {"correlation_id": state.get("correlation_id"), "candidate_count": len(candidates)},
            state,
        )

        return {
            "retrieved_candidates": candidates,
            "status": AgentStatus.SUCCESS.value,
        }
