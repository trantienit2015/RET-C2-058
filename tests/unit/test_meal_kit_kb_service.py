from src.services.meal_kit_kb_service import MealKitKBService


class TestMealKitKBServiceStubCatalog:
    """Regression: `_catalog` must never be empty in the no-vector_store (provisional
    STG) path — an empty catalog makes `hybrid_search()` always return [], which
    fails PlanAssembleNode's "no retrieved candidates" check downstream (deploy-stg
    evidence assertion `agent_status_success`)."""

    def test_default_catalog_is_seeded(self):
        svc = MealKitKBService()
        assert len(svc._catalog) > 0

    def test_hybrid_search_returns_candidates_for_free_text_query(self):
        svc = MealKitKBService()
        candidates = svc.hybrid_search(
            "Plan 3 dinners for this week that are high in protein and avoid shellfish", top_k=5
        )
        assert len(candidates) > 0
        assert all("name" in c and "allergens" in c and "nutrition" in c for c in candidates)

    def test_hybrid_search_uses_injected_vector_store_when_present(self):
        class _FakeVectorStore:
            def similarity_search(self, query, k=5):
                return [{"name": "fake-hit", "allergens": [], "nutrition": {}}]

        svc = MealKitKBService(vector_store=_FakeVectorStore())
        candidates = svc.hybrid_search("anything", top_k=5)
        assert candidates == [{"name": "fake-hit", "allergens": [], "nutrition": {}}]
