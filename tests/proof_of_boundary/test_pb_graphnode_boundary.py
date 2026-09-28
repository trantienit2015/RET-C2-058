# PB-6 (GraphNode boundary companion): PB-6 discovers concrete BaseNode subclasses
# under src/nodes/ only. MealKitPlanningGraphNode lives in src/graph/graph.py by
# design (scaffold canonical for a Cat 2 outer main slot), which puts it outside
# PB-6's discovery scope. It is still a real security boundary — the first node in
# the outer backbone to receive caller input — so this file probes it directly
# instead of leaving it untested.

from framework.schemas.trust_level import TrustLevel

from src.graph.graph import MealKitPlanningGraphNode


class TestGraphNodeS1TrustGate:
    """S-1: caller below required_trust_level must be denied before execute()."""

    def test_denies_caller_below_required_trust_level(self, monkeypatch):
        node = MealKitPlanningGraphNode()
        assert node.required_trust_level == TrustLevel.ANONYMOUS

        # Force required_trust_level above ANONYMOUS for this instance's class to
        # prove the gate actually discriminates (this template's real required
        # level is ANONYMOUS, the least-privileged value — there is no lower
        # level to test denial against, so we raise the bar for the assertion).
        monkeypatch.setattr(MealKitPlanningGraphNode, "required_trust_level", TrustLevel.VERIFIED_EXTERNAL)

        called = {"execute": False}
        monkeypatch.setattr(
            MealKitPlanningGraphNode,
            "execute",
            lambda self, state: called.__setitem__("execute", True) or {"status": "success"},
        )

        state = {"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "plan 3 dinners"}
        result = node(state)

        assert called["execute"] is False
        assert result["status"] == "error"
        assert any("S-1 trust gate denied" in msg for msg in result.get("error_log", []))

    def test_allows_caller_meeting_required_trust_level(self):
        node = MealKitPlanningGraphNode()
        state = {"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "plan 3 dinners with no shellfish"}
        result = node(state)
        assert result.get("status") != "error" or "S-1 trust gate denied" not in "".join(result.get("error_log", []))


class TestGraphNodeBoundaryMapping:
    """extract_input()/merge_output() must map fields explicitly, not pass-through raw dicts (criterion #9)."""

    def test_extract_input_prefers_validated_input_over_raw_user_input(self):
        node = MealKitPlanningGraphNode()
        state = {
            "validated_input": '{"query": "plan 3 dinners", "declared_allergens": ["shellfish"]}',
            "user_input": "raw unvalidated text should not leak through when validated_input is present",
            "correlation_id": "pb-graphnode-test",
            "declared_allergens": ["shellfish"],
        }
        extracted = node.extract_input(state)
        assert extracted == state["validated_input"]
        assert "raw unvalidated text" not in extracted

    def test_merge_output_maps_fields_explicitly_no_raw_passthrough(self):
        node = MealKitPlanningGraphNode()
        sub_result = {
            "query_intent": "planning",
            "retrieved_candidates": [{"name": "rice"}],
            "draft_plan": {"ingredients": [{"name": "rice"}], "steps": [], "nutrition": {}},
            "allergen_warnings": [],
            "final_plan": {"ingredients": [{"name": "rice"}], "warnings": []},
            "status": "success",
            "node_history": ["RecipeIntentClassifyNode", "HybridRetrieveNode"],  # inner-only bookkeeping
            "execution_time": {"RecipeIntentClassifyNode": 0.001},  # inner-only bookkeeping
        }
        merged = node.merge_output({}, sub_result)

        # explicit domain fields land in the merge
        for key in ("query_intent", "retrieved_candidates", "draft_plan", "allergen_warnings", "final_plan", "status"):
            assert key in merged

        # inner-only bookkeeping fields are NOT passed through raw
        assert "node_history" not in merged
        assert "execution_time" not in merged


class TestGraphNodeDelegatedGating:
    """Delegation is a deliberate design choice — the inner entry node performs
    the S-2/S-3 gating that GraphNode.__call__() itself intentionally skips
    (see framework/nodes/graph_node.py + the class docstrings in src/graph/graph.py
    and src/graph/domain_workflow_graph.py)."""

    def test_inner_entry_node_declares_trust_level(self):
        from src.nodes.recipe_intent_classify_node import RecipeIntentClassifyNode

        assert RecipeIntentClassifyNode.required_trust_level == TrustLevel.ANONYMOUS
