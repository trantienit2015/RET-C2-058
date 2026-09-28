"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph (inner subgraph)"""

# Inner graph for the Cat 2 meal-kit planning workflow. Instantiated by
# MealKitPlanningGraphNode.get_subgraph() in src/graph/graph.py.
#
# Pipeline (linear):
#   START → recipe_intent_classify → hybrid_retrieve → plan_assemble
#         → allergen_hard_filter → END

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.nodes.recipe_intent_classify_node import RecipeIntentClassifyNode
from src.nodes.hybrid_retrieve_node import HybridRetrieveNode
from src.nodes.plan_assemble_node import PlanAssembleNode
from src.nodes.allergen_hard_filter_node import AllergenHardFilterNode
from src.schemas.state import State


class MealKitPlanningWorkflowGraph(BaseGraph):
    """Inner graph for the meal-kit planning domain workflow.

    Inherits BaseGraph directly (fully custom topology, no
    pre_process/main/post_process slots). Called by
    MealKitPlanningGraphNode.get_subgraph() in graph.py.
    """

    @property
    def name(self) -> str:
        return "meal_kit_planning_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config keys; top_k/llm/vector_store are optional and
        # defaulted by the individual nodes.
        pass

    def register_nodes(self) -> None:
        # No super() call — BaseGraph.register_nodes() is abstract.
        # Do NOT register initialize/finalize (outer backbone concern).
        top_k = self.config.get("top_k", 5) if hasattr(self, "config") else 5
        llm = self.config.get("llm") if hasattr(self, "config") else None
        vector_store = self.config.get("vector_store") if hasattr(self, "config") else None

        self._nodes["recipe_intent_classify"] = RecipeIntentClassifyNode(llm=llm)
        self._nodes["hybrid_retrieve"] = HybridRetrieveNode(top_k=top_k, vector_store=vector_store)
        self._nodes["plan_assemble"] = PlanAssembleNode(llm=llm)
        self._nodes["allergen_hard_filter"] = AllergenHardFilterNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "recipe_intent_classify")
        self._sg.add_edge("recipe_intent_classify", "hybrid_retrieve")
        self._sg.add_edge("hybrid_retrieve", "plan_assemble")
        self._sg.add_edge("plan_assemble", "allergen_hard_filter")
        self._sg.add_edge("allergen_hard_filter", END)

    def route(self, state: AgentState) -> str:
        # Required by BaseGraph ABC; this topology is linear (never called
        # unless add_conditional_edges() is added later).
        return END if state.get("status") == AgentStatus.ERROR.value else "allergen_hard_filter"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "query_intent": state.get("query_intent"),
            "retrieved_candidates": state.get("retrieved_candidates", []),
            "draft_plan": state.get("draft_plan", {}),
            "allergen_warnings": state.get("allergen_warnings", []),
            "final_plan": state.get("final_plan", {}),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
