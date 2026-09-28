"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph (inner node)"""

# S-3 PRESERVATION VARIANT (non-suppressible, life-safety):
# This node is the last line of defence before the plan leaves the graph.
# 1. Any ingredient still in the draft plan that contains a declared allergen
#    is removed from the final plan (PlanAssembleNode should already have
#    excluded it; this is the backstop).
# 2. Every excluded ingredient (by PlanAssembleNode or here) gets a warning in
#    THIS node's own output. If a warning would be missing, or a conflicting
#    ingredient would remain in the final plan, the node fails closed
#    (AgentStatus.ERROR.value) instead of shipping the plan. See
#    tests/proof_of_boundary/test_pb_allergen_preservation.py.
#
# emit_trace_event payloads carry COUNTS only — never allergen names or
# ingredient identifiers (declared_allergens is session-scoped input and
# must never be logged by value).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.planning_service import nutritional_summary


class AllergenHardFilterNode(FunctionNode):
    """Non-suppressible allergen exclusion + warning-preservation gate for the final plan."""

    # S-1: inner subgraph node — trust authenticated once at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner topology is linear (no conditional routing) — an upstream node
        # error must not be silently overwritten by this node's own SUCCESS.
        if state.get("status") == AgentStatus.ERROR.value:
            return {}

        draft_plan = state.get("draft_plan", {}) or {}
        declared_allergens = {a.lower() for a in (state.get("declared_allergens", []) or [])}
        ingredients = draft_plan.get("ingredients", []) or []

        remaining = self._find_conflicts(ingredients, declared_allergens)
        remaining_names = {name for name, _ in remaining}
        safe_ingredients = [ing for ing in ingredients if ing.get("name", "unknown ingredient") not in remaining_names]

        conflicts = self._merge_conflicts(draft_plan.get("excluded", []) or [], remaining)
        warnings = self._build_warnings(conflicts)

        missing = [c for c in conflicts if not self._warning_present(c, warnings)]
        if missing:
            # Never silently drop an allergen warning — fail closed.
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"allergen warning suppressed for {len(missing)} ingredient(s) — plan blocked"],
            }
        if self._find_conflicts(safe_ingredients, declared_allergens):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["declared allergen still present in the final plan — plan blocked"],
            }
        if not safe_ingredients:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["no allergen-safe ingredient left in the plan — plan blocked"],
            }

        emit_trace_event(
            "allergen_hard_filter_applied",
            {
                "correlation_id": state.get("correlation_id"),
                "warning_count": len(warnings),
                "removed_count": len(remaining),
            },
            state,
        )

        final_plan = {
            **draft_plan,
            "warnings": warnings,
            "excluded": [{"name": name, "allergens": allergens} for name, allergens in conflicts],
        }
        if remaining:
            final_plan["ingredients"] = safe_ingredients
            final_plan["steps"] = [f"Prepare {ing.get('name', 'ingredient')}" for ing in safe_ingredients]
            final_plan["nutrition"] = nutritional_summary(safe_ingredients)
        return {
            "allergen_warnings": warnings,
            "final_plan": final_plan,
            "status": AgentStatus.SUCCESS.value,
        }

    def _find_conflicts(
        self, ingredients: list[dict[str, Any]], declared_allergens: set[str]
    ) -> list[tuple[str, list[str]]]:
        conflicts: list[tuple[str, list[str]]] = []
        for ing in ingredients:
            name = ing.get("name", "unknown ingredient")
            item_allergens = {a.lower() for a in ing.get("allergens", [])}
            hit = sorted(item_allergens & declared_allergens)
            if hit:
                conflicts.append((name, hit))
        return conflicts

    @staticmethod
    def _merge_conflicts(
        excluded: list[dict[str, Any]], remaining: list[tuple[str, list[str]]]
    ) -> list[tuple[str, list[str]]]:
        merged: list[tuple[str, list[str]]] = []
        seen: set[str] = set()
        entries = [
            (e.get("name", "unknown ingredient"), list(e.get("allergens", []))) for e in excluded if isinstance(e, dict)
        ]
        for name, allergens in entries + remaining:
            if name not in seen:
                seen.add(name)
                merged.append((name, sorted(a.lower() for a in allergens)))
        return merged

    def _build_warnings(self, conflicts: list[tuple[str, list[str]]]) -> list[str]:
        return [
            f"{name} excluded from the plan: contains declared allergen(s): {', '.join(allergens)}"
            for name, allergens in conflicts
        ]

    def _warning_present(self, conflict: tuple[str, list[str]], warnings: list[str]) -> bool:
        name, allergens = conflict
        return any(name in w and all(a in w for a in allergens) for w in warnings)
