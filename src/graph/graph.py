"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

# Cat 2 — Cashierless-CVS meal-kit Q&A / recipe planning.
#
# Outer graph (this file): AgentBaseGraph, fixed 5-node backbone.
#   START → initialize → pre_process → main(GraphNode) → post_process → finalize → END
# `main` wraps the inner domain workflow (src/graph/domain_workflow_graph.py):
#   RecipeIntentClassify → HybridRetrieve → PlanAssemble → AllergenHardFilter → END
#
# MealKitPlanningGraphNode is defined in THIS file (not under src/nodes/):
# PB-6 (tests/proof_of_boundary/test_pb_invoke_order.py)
# auto-discovers every BaseNode subclass under src/nodes/ and asserts the standard
# S-1→S-4→S-2→execute→S-3→S-4 lifecycle, which GraphNode intentionally does not
# follow (it delegates gating to the inner subgraph).

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.nodes.pre_process_node import PreProcessNode
from src.nodes.post_process_node import PostProcessNode
from src.schemas.state import State


class MealKitPlanningGraphNode(GraphNode):
    """Wraps the inner meal-kit planning workflow; assigned to the `main` slot."""

    # S-1: outer main-slot wrapper — first node in outer backbone receiving
    # caller input (matches agent.yaml required_trust_level + sibling
    # pre/post_process outer nodes). Inner subgraph nodes stay ANONYMOUS (3b).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, top_k: int = 5, llm: Any = None, vector_store: Any = None):
        super().__init__()
        self._top_k = top_k
        self._llm = llm
        self._vector_store = vector_store

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import MealKitPlanningWorkflowGraph

        sg = MealKitPlanningWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the
        # inner subgraph. Counts only — never the allergen names themselves.
        emit_trace_event(
            "meal_kit_planning_dispatched",
            {
                "correlation_id": state.get("correlation_id"),
                "allergen_count": len(state.get("declared_allergens", []) or []),
            },
            state,
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome.
        emit_trace_event(
            "meal_kit_planning_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "allergen_warning_count": len(sub_result.get("allergen_warnings", []) or []),
            },
            state,
        )
        return {
            "query_intent": sub_result.get("query_intent"),
            "retrieved_candidates": sub_result.get("retrieved_candidates", []),
            "draft_plan": sub_result.get("draft_plan", {}),
            "allergen_warnings": sub_result.get("allergen_warnings", []),
            "final_plan": sub_result.get("final_plan", {}),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"top_k": self._top_k, "llm": self._llm, "vector_store": self._vector_store}


class MealKitPlanningGraph(AgentBaseGraph):
    """Outer Cat 2 graph — cashierless-CVS meal-kit planning agent."""

    @property
    def name(self) -> str:
        return "ret-c2-058"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        top_k = self.config.get("top_k", 5)
        llm = self.config.get("llm")
        vector_store = self.config.get("vector_store")
        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = MealKitPlanningGraphNode(top_k=top_k, llm=llm, vector_store=vector_store)
        self._nodes["post_process"] = PostProcessNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


Graph = MealKitPlanningGraph  # alias for agent.yaml module:"src.graph"
