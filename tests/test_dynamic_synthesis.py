from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.coding_agent.reasoning_engine import CodingAgentReasoner
from repo_investigator.models.command_spec import (
    ExecutionDirective,
    ActionType,
    ArchitecturalInvariant,
    InvariantType,
)
from repo_investigator.llm.base import BaseReasoningEngine

class MockLiveLLMEngine(BaseReasoningEngine):
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def reason(self, prompt: str, system_prompt: str | None = None, response_format: str | None = None, cache_breakpoint: bool = False) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.responses:
            return self.responses.pop(0)
        return "def fallback(): pass"

def test_dynamic_code_synthesis_success(tmp_path: Path):
    valid_python = (
        "```python\n"
        "class DynamicService:\n"
        "    def execute(self):\n"
        "        return 'dynamically_generated'\n"
        "```"
    )
    engine = MockLiveLLMEngine([valid_python])
    reasoner = CodingAgentReasoner(engine=engine)

    directive = ExecutionDirective(
        step_number=1,
        action_type=ActionType.CREATE_FILE,
        target_file="dynamic_service.py",
        target_symbol="DynamicService",
        instruction="Generate dynamic service",
    )
    invariants = [
        ArchitecturalInvariant(
            id="INV-001",
            invariant_type=InvariantType.IMPORT_RESTRICTION,
            rule="No external persistence in core",
            enforcement_scope="core.*",
            verification_heuristic="Check import statements",
        )
    ]

    trace, code = reasoner.reason_step(directive, invariants, tmp_path)
    assert trace.ast_validation_passed is True
    assert code is not None
    assert "DynamicService" in code
    assert "dynamically_generated" in code
    assert any("Dynamic LLM code synthesis succeeded" in log for log in trace.reasoning_chain_of_thought)

def test_dynamic_code_synthesis_autorepair_on_syntax_error(tmp_path: Path):
    invalid_syntax = "```python\ndef broken(\n```"
    valid_syntax = (
        "```python\n"
        "class RepairedService:\n"
        "    def run(self):\n"
        "        return True\n"
        "```"
    )
    engine = MockLiveLLMEngine([invalid_syntax, valid_syntax])
    reasoner = CodingAgentReasoner(engine=engine)

    directive = ExecutionDirective(
        step_number=2,
        action_type=ActionType.REFACTOR_FUNCTION,
        target_file="repaired_service.py",
        target_symbol="RepairedService",
        instruction="Test syntax auto repair",
    )

    trace, code = reasoner.reason_step(directive, [], tmp_path)
    assert trace.ast_validation_passed is True
    assert code is not None
    assert "RepairedService" in code
    assert any("Auto-repair turn succeeded" in log for log in trace.reasoning_chain_of_thought)

def test_dynamic_synthesis_fallback_on_unrecoverable_error(tmp_path: Path):
    unrecoverable = "Not a python block and invalid syntax @@##$$"
    engine = MockLiveLLMEngine([unrecoverable, unrecoverable])
    reasoner = CodingAgentReasoner(engine=engine)

    directive = ExecutionDirective(
        step_number=3,
        action_type=ActionType.CREATE_FILE,
        target_file="fallback_service.py",
        target_symbol="FallbackService",
        instruction="Test fallback to template",
    )

    trace, code = reasoner.reason_step(directive, [], tmp_path)
    assert trace.ast_validation_passed is True
    assert code is not None
    # Verifies fallback template was used
    assert "FallbackService" in code

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
