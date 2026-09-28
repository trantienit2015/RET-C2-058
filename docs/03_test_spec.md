# Test Specification — RET-C2-058 MealKitPlanningAgent

## Test Strategy
- Coverage target: every node ≥1 unit success + ≥1 error/edge; full graph ≥1 integration compile+invoke
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) / Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict, all fields `NotRequired[...]` | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Invalid input (empty query) → `AgentStatus.ERROR` | Error returned, no exception | PASS |
| TC-03 | No JWT/Credential in State/source | CI `gate-credential-scan`: 0 violations | PASS (CI) |
| TC-04 | InvocationContext via configurable/ctx only | No State storage of InvocationContext | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start`/`node_complete`/`node_error` absent from `execute()` body | PASS |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` at class definition if overridden — none of our nodes override it | PASS |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | Same as TC-06 | PASS |
| TC-08 | `required_trust_level` declared on every node | `ClassVar[TrustLevel]` explicit on all 6 `FunctionNode` subclasses (`ANONYMOUS`, matching agent.yaml + inner-node rule) | PASS |
| TC-09 | N/A — no domain-specific `_extra_security_gate_input()` needed (default PII scan sufficient) | — | N/A |
| TC-10 | S-3 preservation-variant check inside `AllergenHardFilterNode.execute()` (not a `_extra_*` hook — explicit business logic) | Warning suppression detected → `AgentStatus.ERROR` | PASS (`tests/unit/test_allergen_hard_filter_node.py::test_error_when_warning_would_be_suppressed`) |
| TC-11 | S-4: ≥1 domain `emit_trace_event()` inside each `execute()` | `meal_kit_query_validated` / `meal_kit_planning_dispatched` / `recipe_intent_classified` / `meal_kit_kb_retrieved` / `meal_kit_plan_assembled` / `allergen_hard_filter_applied` / `meal_kit_planning_completed` / `meal_kit_plan_formatted` — 1 per node minimum | PASS |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass (`test_state_safety.py`) | PASS |
| PB-3 | L1 → External service (meal-kit KB) | `HybridRetrieveNode` via `MealKitKBService.hybrid_search()`, real client injectable via `vector_store` config | PASS (fake client in tests; real client wiring documented in `docs/07_operation_guide.md`) |
| PB-4 | Import isolation | No Level 0 imports (`test_import_isolation.py`) | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint; `declared_allergens` is plain `list[str]` (session-scoped, msgpack-safe) | Inspection pass | PASS |
| PB-6 | Invoke execution order | `test_pb_invoke_order.py` (scaffold-provided) — auto-discovers every `FunctionNode` under `src/nodes/`; `MealKitPlanningGraphNode` deliberately lives in `src/graph/graph.py` so it is NOT discovered (GraphNode delegates gating to the inner subgraph) | Order verified for all 6 nodes | PASS |
| PB-life-safety | Allergen warning preservation (`test_pb_allergen_preservation.py`, new) | An allergen warning present in input (declared_allergens ∩ ingredient allergens) is never absent from `AllergenHardFilterNode`'s own output; a simulated regression that would drop a warning fails closed (`AgentStatus.ERROR`) instead of shipping an incomplete plan | PASS |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Intent classification (LLM + keyword fallback) | "replace the shrimp" / "how many calories in this?" | `substitution` / `nutritional` | PASS |
| BL-02 | Ingredient substitution avoids declared allergens when a safe substitute exists | shrimp (shellfish) + tofu candidate, declared_allergens=[shellfish] | tofu selected, shrimp excluded | PASS |
| BL-03 | No allergen-safe candidate → no plan (a conflicting ingredient is never kept) | shrimp only candidate, declared_allergens=[shellfish] | `status=error`, no `draft_plan` | PASS |
| BL-04 | Full graph integration — success (no conflict) | tofu query, declared_allergens=[shellfish] | `status=success`, `allergen_warnings=[]` | PASS |
| BL-05 | Full graph integration — allergen conflict excluded end-to-end | shrimp + tofu candidates, declared_allergens=[shellfish] | `status=success`, plan = tofu only, 1 exclusion warning | PASS |
| BL-07 | Allergen declared only in the request text | "Plan 3 high-protein dinners and avoid shellfish", no input_context | shellfish item excluded from the plan, 1 warning; without the phrase the item is allowed | PASS |
| BL-08 | Text + context allergens merged | "dairy-free dinners please, no shrimp" + context [Shellfish, egg] | declared_allergens = [shellfish, egg, milk] | PASS |
| BL-06 | Full graph integration — empty input | `""` | `status` = error or cancelled | PASS |

## Test Execution Summary
- Execution date: see CI pipeline for MR `feature/scaffold-init` → `develop`
- Total tests: 6 unit files (pre_process, post_process, recipe_intent_classify, hybrid_retrieve,
  plan_assemble, allergen_hard_filter) + graph_node unit test + 1 integration file + 4 PB files
- Pass / Fail / Skip: see CI job `run-tests` output
- Coverage: all 6 business/outer nodes + GraphNode wrapper covered by ≥1 success + ≥1 error/edge case
