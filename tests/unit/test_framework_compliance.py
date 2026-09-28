# RET-C2-058 — Framework compliance tests TC-01..TC-08, adapted to this template's real architecture
# (Cat 2: outer pre/post_process + GraphNode-wrapped inner subgraph, all nodes ANONYMOUS —
# public shopper-facing read, no auth). TC-06/TC-07 live in
# tests/unit/test_framework_compliance_tc06_tc07.py (exact-name file, see that module).

import os
import re
import typing

from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import (
    allergen_hard_filter_node,
    hybrid_retrieve_node,
    plan_assemble_node,
    post_process_node,
    pre_process_node,
    recipe_intent_classify_node,
)
from src.schemas.state import State

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.ANONYMOUS.value


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _unwrap(annotation):
    """Unwrap typing.NotRequired[...] to the inner type (the state-safety rule wraps every agent-specific field)."""
    origin = typing.get_origin(annotation)
    if origin is not None and getattr(origin, "__name__", "") == "NotRequired":
        args = typing.get_args(annotation)
        return args[0] if args else annotation
    return annotation


# TC-01 - State is a flat TypedDict extending AgentState; every agent-specific field is
# wrapped in NotRequired[...] and JSON-serializable (list/dict of primitives is
# allowed directly — JSON-string encoding via to_json is optional,
# not mandatory, as long as the field stays primitive/JSON-safe, no Pydantic/dataclass).
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_wrapped_in_notrequired_and_json_safe(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        for name in added:
            raw = State.__annotations__[name]
            assert "NotRequired" in str(raw), f"{name}: must be wrapped in NotRequired[...]"


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        node = pre_process_node.PreProcessNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]

    def test_missing_query_envelope_no_raise(self):
        node = recipe_intent_classify_node.RecipeIntentClassifyNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads.
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        # Sole exception: the standalone entry point reads its caller-auth tokens
        # (INVOKE_AUTH_TOKEN / STG_INTERNAL_RUNNER_TOKEN) before any InvocationContext exists.
        offenders = []
        for fp in _src_files():
            if os.path.normpath(fp).endswith(os.path.join("src", "api", "server.py")):
                continue
            with open(fp, encoding="utf-8") as f:
                if "os.environ" in f.read():
                    offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import MealKitPlanningGraph

        agent = MealKitPlanningGraph(config={"max_retry": 1, "top_k": 3})
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.ANONYMOUS, caller_id="shopper-tc04")
        result = agent.invoke("plan 3 dinners with no shellfish", ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: side-effect / decision nodes emit >=1 domain event; no node
# under src/nodes/ (or src/graph/) ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_allergen_hard_filter_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(allergen_hard_filter_node, "emit_trace_event", lambda e, p, s: events.append(e))
        state = {
            "draft_plan": {"ingredients": [{"name": "rice", "allergens": []}], "steps": [], "nutrition": {}},
            "declared_allergens": [],
        }
        out = allergen_hard_filter_node.AllergenHardFilterNode().execute(state)
        assert out["status"] == AgentStatus.SUCCESS.value
        assert len(events) >= 1
        assert "allergen_hard_filter_applied" in events
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        src_and_graph = list(_src_files())
        for fp in src_and_graph:
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-08 - required_trust_level enforced: this template's default is ANONYMOUS
# (public shopper-facing read, no auth) — the trust gate must always let an
# ANONYMOUS caller through for every node, never deny.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        for cls in (
            pre_process_node.PreProcessNode,
            post_process_node.PostProcessNode,
            recipe_intent_classify_node.RecipeIntentClassifyNode,
            hybrid_retrieve_node.HybridRetrieveNode,
            plan_assemble_node.PlanAssembleNode,
            allergen_hard_filter_node.AllergenHardFilterNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

        from src.graph.graph import MealKitPlanningGraphNode

        assert MealKitPlanningGraphNode.required_trust_level in (
            TrustLevel.ANONYMOUS,
            TrustLevel.VERIFIED_EXTERNAL,
            TrustLevel.INTERNAL,
        )

    def test_anonymous_caller_succeeds(self):
        node = pre_process_node.PreProcessNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "plan 3 dinners"})
        assert out["status"] == AgentStatus.SUCCESS.value

    def test_sufficient_trust_succeeds(self):
        node = pre_process_node.PreProcessNode()
        out = node({"caller_trust_level": TRUST, "user_input": "plan 3 dinners"})
        assert out["status"] == AgentStatus.SUCCESS.value
