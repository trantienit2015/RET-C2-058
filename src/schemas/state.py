"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict — never Pydantic BaseModel.
# LangGraph checkpoints use msgpack serialization; Pydantic objects
# cause silent corruption. Extend AgentState with agent-specific
# fields only. Do NOT add credentials, secrets, or Pydantic models.
#
# RET-C2-058 MealKitPlanningGraph — cashierless-CVS meal-kit Q&A / recipe
# planning agent. Declared allergens are SESSION-SCOPED input only (never
# persisted beyond the single invocation, never logged by name via S-4 —
# see AllergenHardFilterNode / emit_trace_event calls which log counts only).

from typing import NotRequired

from framework.schemas.agent_state import AgentState


# Type-check note: the wheel ships no py.typed, so mypy resolves AgentState to Any
# and reports every NotRequired below as valid-type. The fields are correct (the state
# contract requires NotRequired) -- the report is a packaging artifact, suppressed per field.
# Drop these ignores once the wheel ships py.typed.
class State(AgentState):
    """Agent state for the meal-kit planning Cat 2 workflow.

    All agent-specific fields are NotRequired[...] (state-safety rule): a field may be
    absent from the checkpoint (msgpack) or unset when an earlier node in the
    pipeline errors out before writing it.
    """

    # -- outer pre_process output --
    declared_allergens: NotRequired[list[str]]  # type: ignore[valid-type]  # session-scoped only, never persisted
    validated_query: NotRequired[str]  # type: ignore[valid-type]

    # -- merged back from the inner subgraph (via GraphNode.merge_output) --
    query_intent: NotRequired[str]  # type: ignore[valid-type]
    retrieved_candidates: NotRequired[list[dict]]  # type: ignore[valid-type]
    draft_plan: NotRequired[dict]  # type: ignore[valid-type]
    allergen_warnings: NotRequired[list[str]]  # type: ignore[valid-type]
    final_plan: NotRequired[dict]  # type: ignore[valid-type]
