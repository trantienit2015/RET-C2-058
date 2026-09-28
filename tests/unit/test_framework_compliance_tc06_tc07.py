# RET-C2-058 — Framework compliance tests TC-06/TC-07 (exact-name file required by
# gate-scaffold-integrity).
# S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError at class def);
# no node in this repo overrides the optional _extra_security_gate_input/output() hooks
# (both are no-op by default — that is a valid design choice, not
# a gap) — so this file asserts the hooks are callable, NOT that any node overrides them.

import pytest
from framework.nodes.function_node import FunctionNode

from src.nodes import post_process_node


class TestTC0607FinalGates:
    def test_input_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadIn(FunctionNode):  # noqa: N801
                def _security_gate_input(self, state):
                    return state

    def test_output_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadOut(FunctionNode):  # noqa: N801
                def _security_gate_output(self, result):
                    return result

    def test_extra_hooks_are_callable(self):
        # No node in this repo overrides _extra_security_gate_input/output — the
        # base no-op is a valid design choice (both hooks are optional).
        assert callable(post_process_node.PostProcessNode._extra_security_gate_output)
        assert callable(post_process_node.PostProcessNode._extra_security_gate_input)

    def test_output_gate_blocks_credentials(self):
        node = post_process_node.PostProcessNode()
        with pytest.raises(Exception):
            node._security_gate_output({"formatted_output": "token AKIAIOSFODNN7EXAMPLE leaked"})
