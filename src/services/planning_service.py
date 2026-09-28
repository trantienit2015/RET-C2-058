"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

# Deterministic service functions called from PlanAssembleNode. These are
# plain Python functions (Tools per the Agent-vs-Tool boundary), NOT separate
# Agent templates and NOT separate graph nodes.

from __future__ import annotations

from typing import Any


def ingredient_substitute_search(
    ingredient: str,
    declared_allergens: list[str] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return substitute ingredients for `ingredient` that avoid `declared_allergens`.

    `candidates` is the substitute catalog to filter (injected by the caller —
    e.g. a KB lookup result); when omitted, returns an empty list (no
    substitutes known) rather than fabricating data.
    """
    declared_allergens = declared_allergens or []
    pool = candidates or []
    safe: list[dict[str, Any]] = []
    for item in pool:
        item_allergens = {a.lower() for a in item.get("allergens", [])}
        if item_allergens.isdisjoint({a.lower() for a in declared_allergens}):
            safe.append(item)
    return safe


def nutritional_summary(ingredients: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate a simple nutritional summary (calories/protein/fat/carbs) for a plan.

    Pure aggregation over the ingredient dicts supplied by the caller —
    no external calls, deterministic.
    """
    totals = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    for ing in ingredients:
        nutrition = ing.get("nutrition", {})
        for key in totals:
            totals[key] += float(nutrition.get(key, 0) or 0)
    return totals
