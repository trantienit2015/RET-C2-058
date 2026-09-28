from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext, TrustLevel
from src.graph.graph import Graph


class _FakeLLM:
    def complete(self, prompt: str) -> str:
        return "planning"


class _FakeVectorStore:
    def __init__(self, results):
        self._results = results

    def similarity_search(self, query: str, k: int = 5):
        return self._results[:k]


def _make_graph(vector_store=None):
    graph = Graph(config={"llm": _FakeLLM(), "vector_store": vector_store, "top_k": 5, "max_retry": 1})
    graph.compile()
    return graph


class TestMealKitPlanningGraph:
    def test_full_pipeline_success_no_allergen_conflict(self):
        vector_store = _FakeVectorStore([{"name": "tofu", "allergens": [], "nutrition": {"calories": 80}}])
        graph = _make_graph(vector_store=vector_store)
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        # get_output() (AgentBaseGraph) surfaces only {output, status, trace_id,
        # correlation_id, node_history} — the formatted plan lives at result["output"].
        result = graph.invoke(
            "what can I make with tofu tonight?",
            ctx=ctx,
            input_context={"declared_allergens": ["shellfish"]},
        )

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["output"]["allergen_warning_count"] == 0
        node_history = result.get("node_history", [])
        assert any("initialize" in str(n).lower() for n in node_history)
        assert any("finalize" in str(n).lower() for n in node_history)

    def test_pipeline_excludes_declared_allergen_and_warns(self):
        vector_store = _FakeVectorStore(
            [
                {"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}},
                {"name": "tofu", "allergens": [], "nutrition": {"calories": 80}},
            ]
        )
        graph = _make_graph(vector_store=vector_store)
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        result = graph.invoke(
            "what can I make with shrimp tonight?",
            ctx=ctx,
            input_context={"declared_allergens": ["shellfish"]},
        )

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["output"]["allergen_warning_count"] == 1
        assert len(result["output"]["plan"]["warnings"]) == 1
        assert [i["name"] for i in result["output"]["plan"]["ingredients"]] == ["tofu"]

    def test_text_declared_allergen_is_excluded_without_input_context(self):
        vector_store = _FakeVectorStore(
            [
                {"name": "shrimp stir-fry", "allergens": ["shellfish"], "nutrition": {"calories": 250}},
                {"name": "grilled chicken", "allergens": [], "nutrition": {"calories": 284}},
            ]
        )
        graph = _make_graph(vector_store=vector_store)
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        result = graph.invoke("Plan 3 high-protein dinners and avoid shellfish", ctx=ctx)

        assert result["status"] == AgentStatus.SUCCESS.value
        names = [i["name"] for i in result["output"]["plan"]["ingredients"]]
        assert names == ["grilled chicken"]
        assert result["output"]["allergen_warning_count"] == 1

    def test_without_declaration_shellfish_is_allowed(self):
        vector_store = _FakeVectorStore(
            [
                {"name": "shrimp stir-fry", "allergens": ["shellfish"], "nutrition": {"calories": 250}},
                {"name": "grilled chicken", "allergens": [], "nutrition": {"calories": 284}},
            ]
        )
        graph = _make_graph(vector_store=vector_store)
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        result = graph.invoke("Plan 3 high-protein dinners", ctx=ctx)

        assert result["status"] == AgentStatus.SUCCESS.value
        names = [i["name"] for i in result["output"]["plan"]["ingredients"]]
        assert "shrimp stir-fry" in names
        assert result["output"]["allergen_warning_count"] == 0

    def test_only_conflicting_candidates_returns_error(self):
        vector_store = _FakeVectorStore(
            [{"name": "shrimp", "allergens": ["shellfish"], "nutrition": {"calories": 100}}]
        )
        graph = _make_graph(vector_store=vector_store)
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        result = graph.invoke("what can I make with shrimp tonight? no shellfish", ctx=ctx)

        assert result["status"] == AgentStatus.ERROR.value

    def test_empty_input_returns_error(self):
        graph = _make_graph()
        ctx = InvocationContext(caller_trust_level=TrustLevel.ANONYMOUS)

        result = graph.invoke("", ctx=ctx, input_context={"declared_allergens": []})

        assert result["status"] in (AgentStatus.ERROR.value, AgentStatus.CANCELLED.value)
