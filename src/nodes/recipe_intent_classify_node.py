"""AgentCore Platform v1.0 — RET-C2-058 MealKitPlanningGraph (inner node)"""

# Inner subgraph node — first step. The inner graph does NOT see the outer
# state; BaseGraph.invoke() seeds initial_state = {"user_input": <str>, ...}.
# This node parses the JSON payload built by the outer PreProcessNode
# (query + declared_allergens) back out of user_input.

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_VALID_INTENTS = {"planning", "substitution", "allergen", "nutritional"}


class _LLMClassifyError(Exception):
    """Raised when a configured LLM fails or returns an unusable classification."""


class RecipeIntentClassifyNode(FunctionNode):
    """Classify the meal-kit query intent (planning/substitution/allergen/nutritional)."""

    # S-1: inner subgraph node — trust authenticated once at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None):
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict) or not payload.get("query"):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RecipeIntentClassifyNode: empty or malformed query payload"],
            }

        query = payload["query"]
        declared_allergens = payload.get("declared_allergens", []) or []

        try:
            intent = self._classify(query)
        except _LLMClassifyError as exc:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"RecipeIntentClassifyNode: LLM classification failed — {exc}"],
            }

        emit_trace_event(
            "recipe_intent_classified",
            {"correlation_id": state.get("correlation_id"), "intent": intent},
            state,
        )

        return {
            "validated_query": query,
            "declared_allergens": list(declared_allergens),
            "query_intent": intent,
            "status": AgentStatus.SUCCESS.value,
        }

    def _classify(self, query: str) -> str:
        # Deterministic keyword fallback is only valid when NO llm is configured
        # at all. A configured-but-failing LLM must surface as an error instead
        # (see the `is None` branch below vs. the `_LLMClassifyError` raises).
        if self._llm is None or not hasattr(self._llm, "complete"):
            return self._keyword_fallback(query)

        # Canonical BaseLLM.complete(messages: list) -> dict.
        try:
            raw = self._llm.complete([{"role": "user", "content": f"Classify intent for meal-kit query: {query}"}])
        except Exception as exc:  # noqa: BLE001 — provider/transport error, normalized to _LLMClassifyError below
            raise _LLMClassifyError(str(exc)) from exc
        response = self._extract_text(raw).strip().lower()
        if not response:
            raise _LLMClassifyError("empty or unparseable LLM response")
        if response in _VALID_INTENTS:
            return response
        raise _LLMClassifyError(f"LLM returned an unrecognized intent: {response!r}")

    @staticmethod
    def _keyword_fallback(query: str) -> str:
        q = query.lower()
        if "allerg" in q:
            return "allergen"
        if "substitut" in q or "replace" in q or "instead" in q:
            return "substitution"
        if "calorie" in q or "protein" in q or "nutrition" in q:
            return "nutritional"
        return "planning"

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, dict):
            content = raw.get("content", "")
            return content if isinstance(content, str) else ""
        if isinstance(raw, str):
            return raw
        return ""
