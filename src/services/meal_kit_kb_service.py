"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph"""

# Deterministic KB retrieval service — hybrid (keyword + dense vector) search
# over the meal-kit KB (SKU catalog / recipe / allergen / nutrition records).
# Plain functions/classes only — no agenticstar imports, no State, no
# security gates (Tool, per Agent-vs-Tool boundary; the Agent is the graph
# that wraps this with State + InvocationContext + security gates).

from __future__ import annotations

from typing import Any, cast

# Provisional/STG stand-in catalog — used only when no real vector_store/keyword_index
# is injected (the provisional STG mode has no external KB backend available).
# Without this seed, `_fallback_search()` always returns an empty list regardless of
# query, which fails PlanAssembleNode's "no retrieved candidates" check downstream
# (deploy-stg evidence assertion `agent_status_success`). A real deployment replaces
# `keyword_index`/`vector_store` with real clients; this list is never treated as
# production KB data.
_STUB_CATALOG: list[dict[str, Any]] = [
    {
        "name": "grilled chicken breast",
        "allergens": [],
        "nutrition": {"calories": 284, "protein_g": 53, "fat_g": 6, "carbs_g": 0},
    },
    {
        "name": "salmon fillet",
        "allergens": ["fish"],
        "nutrition": {"calories": 367, "protein_g": 39, "fat_g": 22, "carbs_g": 0},
    },
    {
        "name": "shrimp stir-fry",
        "allergens": ["shellfish"],
        "nutrition": {"calories": 250, "protein_g": 24, "fat_g": 9, "carbs_g": 16},
    },
    {
        "name": "tofu vegetable bowl",
        "allergens": ["soy"],
        "nutrition": {"calories": 220, "protein_g": 18, "fat_g": 10, "carbs_g": 20},
    },
    {
        "name": "lentil quinoa salad",
        "allergens": [],
        "nutrition": {"calories": 310, "protein_g": 16, "fat_g": 8, "carbs_g": 45},
    },
    {
        "name": "beef sirloin steak",
        "allergens": [],
        "nutrition": {"calories": 340, "protein_g": 42, "fat_g": 18, "carbs_g": 0},
    },
    {
        "name": "egg fried rice",
        "allergens": ["egg"],
        "nutrition": {"calories": 300, "protein_g": 12, "fat_g": 10, "carbs_g": 40},
    },
    {
        "name": "greek yogurt parfait",
        "allergens": ["milk"],
        "nutrition": {"calories": 180, "protein_g": 15, "fat_g": 4, "carbs_g": 22},
    },
]


class MealKitKBService:
    """Hybrid keyword + dense-vector search over the meal-kit KB.

    A real deployment wires a keyword index (e.g. BM25) and a vector store
    (e.g. Qdrant) here. This reference implementation keeps a small in-memory
    catalog (`_STUB_CATALOG`) so the template is runnable/testable without
    external services; replace `self._catalog` / `self._embed` with real
    client calls.
    """

    def __init__(self, vector_store: Any = None, keyword_index: Any = None) -> None:
        self._vector_store = vector_store
        self._keyword_index = keyword_index
        self._catalog: list[dict[str, Any]] = list(_STUB_CATALOG)

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to `top_k` KB candidates matching `query`.

        `metadata_filter` narrows by SKU/recipe metadata (e.g. category).
        When real `vector_store`/`keyword_index` clients are injected, this
        method should merge + re-rank their results (hybrid retrieval); the
        in-memory fallback here does a simple keyword match for testability.
        """
        if self._vector_store is not None and hasattr(self._vector_store, "similarity_search"):
            candidates = self._vector_store.similarity_search(query, k=top_k)
        else:
            candidates = self._fallback_search(query)

        if metadata_filter:
            candidates = [
                c for c in candidates if all(c.get("metadata", {}).get(k) == v for k, v in metadata_filter.items())
            ]
        return cast(list[dict[str, Any]], candidates[:top_k])

    def _fallback_search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [c for c in self._catalog if q in c.get("name", "").lower()] or list(self._catalog)
