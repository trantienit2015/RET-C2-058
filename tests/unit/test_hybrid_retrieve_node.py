from framework.schemas.agent_status import AgentStatus
from src.nodes.hybrid_retrieve_node import HybridRetrieveNode


class _FakeKBService:
    def __init__(self, results):
        self._results = results
        self.last_query = None
        self.last_top_k = None

    def hybrid_search(self, query, top_k=5, metadata_filter=None):
        self.last_query = query
        self.last_top_k = top_k
        return self._results[:top_k]


class TestHybridRetrieveNode:
    def test_success_returns_candidates(self):
        fake = _FakeKBService([{"name": "shrimp", "allergens": ["shellfish"]}, {"name": "rice", "allergens": []}])
        node = HybridRetrieveNode(top_k=2, kb_service=fake)
        result = node.execute({"validated_query": "shrimp meal kit", "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["retrieved_candidates"]) == 2
        assert fake.last_query == "shrimp meal kit"

    def test_error_on_missing_query(self):
        node = HybridRetrieveNode(kb_service=_FakeKBService([]))
        result = node.execute({"validated_query": "", "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
