import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.recipe_intent_classify_node import RecipeIntentClassifyNode


class _FakeLLM:
    """Legacy fake — returns a bare string (fleet-wide backward-compat shape)."""

    def __init__(self, response: str):
        self._response = response

    def complete(self, messages: list) -> str:
        return self._response


class _DictLLM:
    """Canonical BaseLLM.complete(messages: list) -> {"content": str, ...}."""

    def __init__(self, content: str):
        self._content = content

    def complete(self, messages: list) -> dict:
        return {"content": self._content, "tool_calls": [], "model": "fake", "usage": {}}


class _EmptyContentLLM:
    def complete(self, messages: list) -> dict:
        return {"content": "", "tool_calls": [], "model": "fake", "usage": {}}


class _RaisingLLM:
    def complete(self, messages: list) -> dict:
        raise RuntimeError("provider timeout")


class TestRecipeIntentClassifyNode:
    def test_success_classifies_via_llm(self):
        node = RecipeIntentClassifyNode(llm=_FakeLLM("substitution"))
        payload = json.dumps({"query": "replace the shrimp", "declared_allergens": ["shellfish"]})
        result = node.execute({"user_input": payload, "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.SUCCESS
        assert result["query_intent"] == "substitution"
        assert result["declared_allergens"] == ["shellfish"]
        assert result["validated_query"] == "replace the shrimp"

    def test_success_classifies_via_canonical_dict_llm(self):
        node = RecipeIntentClassifyNode(llm=_DictLLM("substitution"))
        payload = json.dumps({"query": "replace the shrimp", "declared_allergens": ["shellfish"]})
        result = node.execute({"user_input": payload, "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.SUCCESS
        assert result["query_intent"] == "substitution"

    def test_success_falls_back_to_keyword_heuristic_without_llm(self):
        node = RecipeIntentClassifyNode(llm=None)
        payload = json.dumps({"query": "how many calories in this?", "declared_allergens": []})
        result = node.execute({"user_input": payload, "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.SUCCESS
        assert result["query_intent"] == "nutritional"

    def test_error_on_malformed_payload(self):
        node = RecipeIntentClassifyNode()
        result = node.execute({"user_input": "not json", "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_configured_llm_raising_is_error_not_silent_fallback(self):
        # A configured-but-failing LLM must surface as ERROR — never silently
        # degrade to the deterministic keyword fallback (that path is only
        # valid when no LLM is configured at all).
        node = RecipeIntentClassifyNode(llm=_RaisingLLM())
        payload = json.dumps({"query": "how many calories in this?", "declared_allergens": []})
        result = node.execute({"user_input": payload, "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_configured_llm_empty_response_is_error_not_silent_fallback(self):
        node = RecipeIntentClassifyNode(llm=_EmptyContentLLM())
        payload = json.dumps({"query": "how many calories in this?", "declared_allergens": []})
        result = node.execute({"user_input": payload, "correlation_id": "corr-1"})

        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]
