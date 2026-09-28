"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph (inner node)"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.planning_service import ingredient_substitute_search, nutritional_summary


class PlanAssembleNode(FunctionNode):
    """Assemble a multi-step ingredient plan from the retrieved KB candidates.

    Calls the deterministic service functions ingredient_substitute_search()
    and nutritional_summary() (Tools, per the Agent-vs-Tool boundary) — NOT
    separate Agent templates, NOT separate graph nodes.
    """

    # S-1: inner subgraph node — trust authenticated once at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None):
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner topology is linear (no conditional routing) — an upstream node
        # error must not be silently overwritten by this node's own SUCCESS.
        if state.get("status") == AgentStatus.ERROR.value:
            return {}

        candidates = state.get("retrieved_candidates", []) or []
        declared_allergens = state.get("declared_allergens", []) or []

        if not candidates:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PlanAssembleNode: no retrieved candidates to assemble a plan from"],
            }

        declared_lower = {a.lower() for a in declared_allergens}
        selected: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for cand in candidates:
            item_allergens = {a.lower() for a in cand.get("allergens", [])}
            hit = sorted(item_allergens & declared_lower)
            if not hit:
                if not self._already_selected(cand, selected):
                    selected.append(cand)
                continue
            # A conflicting ingredient never enters the plan. It is replaced by
            # a safe substitute that is not already in the plan, or dropped;
            # either way it is recorded in `excluded` so AllergenHardFilterNode
            # (downstream) surfaces a warning for it.
            excluded.append({"name": cand.get("name", "unknown ingredient"), "allergens": hit})
            substitutes = ingredient_substitute_search(cand.get("name", ""), declared_allergens, candidates)
            fresh = [s for s in substitutes if not self._already_selected(s, selected)]
            if fresh:
                selected.append(fresh[0])

        if not selected:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "PlanAssembleNode: every retrieved candidate contains a declared allergen — "
                    "no allergen-safe plan can be assembled"
                ],
            }

        nutrition = nutritional_summary(selected)
        steps = [f"Prepare {ing.get('name', 'ingredient')}" for ing in selected]
        draft_plan = {"ingredients": selected, "steps": steps, "nutrition": nutrition, "excluded": excluded}

        emit_trace_event(
            "meal_kit_plan_assembled",
            {"correlation_id": state.get("correlation_id"), "ingredient_count": len(selected)},
            state,
        )

        return {"draft_plan": draft_plan, "status": AgentStatus.SUCCESS.value}

    @staticmethod
    def _already_selected(item: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
        name = item.get("name")
        return any(s is item or (name is not None and s.get("name") == name) for s in selected)
