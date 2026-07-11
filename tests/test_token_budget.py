import pytest

from specflow.context_builder import BuiltContext, ContextSource
from specflow.token_budget import BudgetPolicy, TokenBudgetError, TokenBudgetManager


def _context(user_message: str, system_message: str = "system") -> BuiltContext:
    return BuiltContext(
        system_message=system_message,
        user_message=user_message,
        sources=[
            ContextSource("project_context", "PROJECT_CONTEXT.md", "project-hash"),
            ContextSource("prompt", "analyze_requirement@1.0.0", "prompt-hash"),
        ],
        estimated_tokens=1,
        prompt_name="analyze_requirement",
        prompt_version="1.0.0",
        prompt_hash="prompt-hash",
        project_context_hash="project-hash",
    )


def _large_message() -> str:
    return "\n".join(
        [
            "Project:",
            "project_name: demo-api",
            "language: python",
            "frameworks: fastapi",
            "Requirement:",
            "Build the token budget manager and preserve this requirement.",
            "technology_evidence:",
            "pyproject.toml: fastapi " + ("evidence " * 80),
            "parse_warnings:",
            "warning: optional parse warning " + ("warning " * 70),
            "unknowns:",
            "unknown: optional missing tool " + ("unknown " * 70),
        ]
    )


def test_small_context_is_fully_retained() -> None:
    context = _context("Project:\nlanguage: python\nRequirement:\nKeep all content")
    result = TokenBudgetManager(BudgetPolicy(max_tokens=500)).apply(context)

    assert not result.was_trimmed
    assert result.context == context
    assert result.removed_sections == []
    assert result.final_estimated_tokens == result.original_estimated_tokens


def test_oversized_context_triggers_trimming() -> None:
    context = _context(_large_message())
    result = TokenBudgetManager(BudgetPolicy(max_tokens=180, reserved_response_tokens=20)).apply(
        context
    )

    assert result.was_trimmed
    assert result.original_estimated_tokens > result.final_estimated_tokens
    assert result.final_estimated_tokens <= result.policy.input_budget
    assert result.removed_sections


def test_priority_retains_requirement_and_project_before_low_priority_sections() -> None:
    context = _context(_large_message())
    result = TokenBudgetManager(BudgetPolicy(max_tokens=180, reserved_response_tokens=20)).apply(
        context
    )

    assert "Build the token budget manager" in result.context.user_message
    assert "project_name: demo-api" in result.context.user_message
    assert "unknown: optional missing tool" not in result.context.user_message
    assert result.removed_sections[0].name == "unknowns"


def test_real_t007_user_requirement_marker_is_high_priority() -> None:
    context = _context(
        "\n".join(
            [
                "technology_evidence:",
                "pyproject.toml: fastapi " + ("evidence " * 80),
                "User requirement:",
                "Preserve the actual user requirement.",
                "unknowns:",
                "unknown: optional missing tool " + ("unknown " * 60),
            ]
        )
    )

    result = TokenBudgetManager(BudgetPolicy(max_tokens=150, reserved_response_tokens=20)).apply(
        context
    )

    assert "Preserve the actual user requirement." in result.context.user_message
    assert any(section.name in {"unknowns", "evidence"} for section in result.removed_sections)


def test_technology_stack_is_a_budget_section() -> None:
    context = _context(
        "\n".join(
            [
                "Project:",
                "project_name: demo-api",
                "language: python " + ("tech " * 80),
                "Requirement:",
                "Preserve requirement.",
                "unknowns:",
                "unknown: optional missing tool " + ("unknown " * 60),
            ]
        )
    )
    policy = BudgetPolicy(
        max_tokens=150,
        reserved_response_tokens=20,
        section_priorities={
            "system_message": 100,
            "requirement": 90,
            "project_overview": 80,
            "unknowns": 70,
            "technology_stack": 10,
            "source_tracking": 60,
            "evidence": 50,
            "warnings": 40,
        },
    )

    result = TokenBudgetManager(policy).apply(context)

    assert result.removed_sections[0].name == "technology_stack"


def test_removed_sections_are_recorded_in_deterministic_order() -> None:
    context = _context(_large_message())
    policy = BudgetPolicy(max_tokens=180, reserved_response_tokens=20)

    first = TokenBudgetManager(policy).apply(context)
    second = TokenBudgetManager(policy).apply(context)

    assert [section.name for section in first.removed_sections] == [
        section.name for section in second.removed_sections
    ]
    assert [section.priority for section in first.removed_sections] == [
        section.priority for section in second.removed_sections
    ]


def test_context_hash_is_stable_for_same_input_and_policy() -> None:
    context = _context(_large_message())
    policy = BudgetPolicy(max_tokens=180, reserved_response_tokens=20)

    first = TokenBudgetManager(policy).apply(context)
    second = TokenBudgetManager(policy).apply(context)

    assert first.context.context_hash == second.context.context_hash
    assert first.context_hash == second.context_hash


def test_custom_priority_policy_changes_trim_order() -> None:
    context = _context(_large_message())
    policy = BudgetPolicy(
        max_tokens=180,
        reserved_response_tokens=20,
        section_priorities={
            "system_message": 100,
            "requirement": 90,
            "project_overview": 80,
            "technology_stack": 70,
            "source_tracking": 60,
            "unknowns": 55,
            "evidence": 50,
            "warnings": 10,
        },
    )

    result = TokenBudgetManager(policy).apply(context)

    assert result.removed_sections[0].name == "warnings"


def test_sensitive_information_does_not_reappear_after_budgeting() -> None:
    context = _context(
        "\n".join(
            [
                "Project:",
                "project_name: demo-api",
                "Requirement:",
                "Use sanitized inputs only",
                "technology_evidence:",
                "config.py: api_key=<redacted>",
            ]
        )
    )

    result = TokenBudgetManager(BudgetPolicy(max_tokens=500)).apply(context)
    combined = "\n".join([result.context.system_message, result.context.user_message])

    assert "sk-" not in combined
    assert "user:pass" not in combined
    assert "api_key=<redacted>" in combined


@pytest.mark.parametrize(
    "policy",
    [
        BudgetPolicy(max_tokens=0),
        BudgetPolicy(max_tokens=100, reserved_response_tokens=100),
        BudgetPolicy(max_tokens=100, reserved_response_tokens=-1),
        BudgetPolicy(max_tokens=100, estimation_chars_per_token=0),
    ],
)
def test_invalid_budget_policy_fails(policy: BudgetPolicy) -> None:
    with pytest.raises(TokenBudgetError):
        TokenBudgetManager(policy)


def test_impossible_budget_fails() -> None:
    context = _context("Project:\nsmall\nRequirement:\nsmall", system_message="system " * 400)

    with pytest.raises(TokenBudgetError):
        TokenBudgetManager(BudgetPolicy(max_tokens=50)).apply(context)
