"""Tests for the planner engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from planner.engine import PlannerEngine


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Create a mock OpenAI client."""
    client = AsyncMock()
    client.chat.completions.create.return_value = ChatCompletion(
        id="test",
        model="gpt-4-turbo-preview",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                finish_reason="function_call",
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=None,
                    function_call={
                        "name": "create_plan_item",
                        "arguments": json.dumps({
                            "file_path": "test.py",
                            "action": "MODIFY",
                            "reason": "Reduce complexity",
                            "confidence": 0.9
                        })
                    }
                )
            )
        ]
    )
    return client


@pytest.fixture
def sample_repo_snapshot() -> Dict[str, Any]:
    """Create a sample repository snapshot for testing."""
    return {
        "files": ["test.py"],
        "asts": {
            "test.py": {
                "complexity": 15,
                "imports": ["outdated_package"]
            }
        },
        "metrics": {
            "max_complexity": 10,
            "outdated_deps": ["outdated_package"],
            "needs_improvement": ["test"]
        }
    }


@pytest.fixture
def planner(mock_openai_client: AsyncMock) -> PlannerEngine:
    """Create a planner engine instance with mocked dependencies."""
    with patch("jinja2.Environment") as mock_env:
        mock_env.return_value.get_template.return_value.render.return_value = "test prompt"
        return PlannerEngine(openai_client=mock_openai_client)


async def test_plan_repo_success(
    planner: PlannerEngine, sample_repo_snapshot: Dict[str, Any]
) -> None:
    """Test successful repository planning."""
    plan_items = await planner.plan_repo(sample_repo_snapshot)
    
    assert len(plan_items) == 1
    item = plan_items[0]
    assert item.file_path == "test.py"
    assert item.action == "MODIFY"
    assert item.reason == "Reduce complexity"
    assert item.confidence == 0.9


async def test_plan_repo_invalid_snapshot(planner: PlannerEngine) -> None:
    """Test handling of invalid repository snapshot."""
    with pytest.raises(ValueError, match="Repo snapshot must be a dictionary"):
        await planner.plan_repo([])  # type: ignore


def test_select_template(planner: PlannerEngine) -> None:
    """Test template selection logic."""
    # Test needs improvement case
    assert planner._select_template(
        "test.py",
        {"complexity": 5},
        {"needs_improvement": ["test"]}
    ) == "add_tests.j2"

    # Test outdated dependencies case
    assert planner._select_template(
        "test.py",
        {"imports": ["old_pkg"]},
        {"outdated_deps": ["old_pkg"]}
    ) == "upgrade_runtime.j2"

    # Test high complexity case
    assert planner._select_template(
        "test.py",
        {"complexity": 15},
        {"max_complexity": 10}
    ) == "refactor.j2"

    # Test no issues case
    assert planner._select_template(
        "test.py",
        {"complexity": 5},
        {"max_complexity": 10}
    ) is None


def test_generate_reason(planner: PlannerEngine) -> None:
    """Test reason generation logic."""
    # Test needs improvement case
    assert "Add test coverage" in planner._generate_reason(
        "test.py",
        {},
        {"needs_improvement": ["test"]}
    )

    # Test high complexity case
    assert "Reduce complexity" in planner._generate_reason(
        "test.py",
        {"complexity": 15},
        {"max_complexity": 10}
    )

    # Test outdated dependencies case
    assert "Update dependencies" in planner._generate_reason(
        "test.py",
        {"imports": ["old_pkg"]},
        {"outdated_deps": ["old_pkg"]}
    )

    # Test default case
    assert planner._generate_reason("test.py", {}, {}) == "General code improvement" 