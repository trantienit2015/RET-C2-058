# Template Design Specification — RET-C2-058 MealKitPlanningAgent

## Position in AgentCore Architecture

- **Agent Class**: `MealKitPlanningGraph` (`src/graph/graph.py`)
- **L1 Base**: `AgentBaseGraph` (L1 direct) — outer graph. Cat 2 wraps the domain
  workflow inside a `GraphNode` (`MealKitPlanningGraphNode`, same file) around an
  inner `BaseGraph` subgraph (`MealKitPlanningWorkflowGraph`, `src/graph/domain_workflow_graph.py`).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`src/schemas/state.py`, all agent-specific fields `NotRequired[...]`)
  - Node: L1 inheritance (`FunctionNode.execute(self, state) -> dict` override only)
  - Graph: composition (`register_nodes()` for outer + inner)

## Architecture Overview

### Outer graph (backbone, fixed)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version/session_id/trust_level setup | — | — | InitializeNode (default) |
| pre_process | validate query; merge `input_context.declared_allergens` with allergen avoidances parsed from the text (`src/services/allergen_declaration.py`, bounded, vocabulary-restricted), canonicalise; build validated_input JSON | `user_input`, `input_context.declared_allergens` | `validated_query`, `declared_allergens`, `validated_input` | `PreProcessNode` |
| main | dispatch to inner subgraph, merge result | `validated_input` | `query_intent`, `retrieved_candidates`, `draft_plan`, `allergen_warnings`, `final_plan` | `MealKitPlanningGraphNode(GraphNode)` |
| post_process | format final output | `final_plan`, `allergen_warnings` | `formatted_output`, `result` | `PostProcessNode` |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Inner subgraph (`MealKitPlanningWorkflowGraph`, `BaseGraph`)

| Node | Responsibility | Input State | Output State |
|------|---------------|-------------|--------------|
| recipe_intent_classify | parse JSON payload from `user_input`, classify intent | `user_input` (JSON str) | `validated_query`, `declared_allergens`, `query_intent` |
| hybrid_retrieve | hybrid keyword+vector retrieval over meal-kit KB | `validated_query` | `retrieved_candidates` |
| plan_assemble | multi-step ingredient selection; a candidate containing a declared allergen is replaced by a safe substitute not already selected, or dropped, and recorded in `draft_plan.excluded`; error when no allergen-safe candidate remains; calls `ingredient_substitute_search()` / `nutritional_summary()` (deterministic Tools in `src/services/planning_service.py`) | `retrieved_candidates`, `declared_allergens` | `draft_plan` |
| allergen_hard_filter | **S-3 preservation-variant gate** (non-suppressible) — removes any conflicting ingredient still in the draft (backstop), warns for every excluded ingredient in its own output; fails closed if a warning would be dropped, a conflict would remain, or no safe ingredient is left | `draft_plan`, `declared_allergens` | `allergen_warnings`, `final_plan` |

### Data Flow

```
OUTER: START → initialize → pre_process → main(GraphNode) → post_process → finalize → END
                                              │ extract_input() → JSON string
                                              ▼
INNER: START → recipe_intent_classify → hybrid_retrieve → plan_assemble
             → allergen_hard_filter → END
                                              │ get_output() → sub_result
                                              ▼ merge_output()
```

Data crosses the outer→inner boundary ONLY as a JSON string (`GraphNode.extract_input`
returns `validated_input`; the inner `recipe_intent_classify` node `json.loads()`s it
back out — the inner graph never sees outer State directly, per `BaseGraph.invoke()`
seeding only `{"user_input": <str>, ...shared fields}`).

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `declared_allergens` | `list[str]` | Session-scoped input only — never persisted beyond the invocation, never logged by value | No |
| `validated_query` | `str` | Sanitized query text | No |
| `query_intent` | `str` | planning / substitution / allergen / nutritional | No |
| `retrieved_candidates` | `list[dict]` | Hybrid-retrieval KB candidates | No |
| `draft_plan` | `dict` | Pre-preservation-gate ingredient plan | No |
| `allergen_warnings` | `list[str]` | Warnings surfaced by the preservation gate | No |
| `final_plan` | `dict` | Final plan returned to the caller | No |

**State Constraints (mandatory):**
- Flat TypedDict only, all agent-specific fields `NotRequired[...]`
- No JWT, API keys, credentials in State
- InvocationContext via `config["configurable"]` only (not in State)
- `declared_allergens` is session-scoped: normal transient graph state during one
  invocation is expected/required for the pipeline to function; it is never written
  to a persistent store beyond the checkpoint of that single invocation, and is
  never included (by value) in any `emit_trace_event()` payload — only counts.

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [x] S-4: `emit_trace_event()` — at least one domain event per node (counts only,
      never allergen names/dietary identifiers)
- [x] S-3 preservation variant: `AllergenHardFilterNode.execute()` removes any
      declared-allergen conflict still in the plan and re-verifies every excluded
      ingredient is reflected by a matching warning in its own returned data —
      fails closed (`AgentStatus.ERROR`) rather than silently dropping a warning or
      shipping a conflicting ingredient (life-safety requirement)

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — `MealKitPlanningGraphNode` wraps
  `MealKitPlanningWorkflowGraph`
- **Composition target**: inner `BaseGraph` domain workflow (4 business nodes)
- **Error propagation strategy**: `propagate` (fail fast — inner errors surface as
  `SubgraphError` to the outer graph; no HITL in this template, so
  `propagate_hitl = False`)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: `framework/` and `shared/` only

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | fixed multi-step workflow, no autonomous loop needed |
| Composition pattern | Flat (Cat 1 style) | GraphNode + inner BaseGraph | GraphNode + inner BaseGraph | Cat 2 requires this per `gate-composition` — see cat2-pattern reference |
| Retrieval strategy | Keyword-only | Hybrid keyword+vector | Hybrid | meal-kit SKU/recipe KB benefits from both exact-match (SKU codes) and semantic recall |
| Allergen gate placement | Filter/redact variant | Preservation variant | Preservation | life-safety requirement — must never silently drop a warning |
