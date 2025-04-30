"""Tests for the planner confidence scoring module."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message import ChatCompletionLogprobs

from planner.scoring import (
    calculate_confidence,
    _calculate_llm_score,
    _calculate_lint_score,
    _calculate_test_score,
)


@pytest.fixture
def mock_message_with_logprobs() -> ChatCompletionMessage:
    """Create a mock message with token logprobs."""
    return ChatCompletionMessage(
        role="assistant",
        content=None,
        function_call=None,
        tool_calls=None,
        logprobs=ChatCompletionLogprobs(
            content=None,
            token_logprobs=[-0.3, -0.2, -0.1],  # High confidence
            tokens=["test", "tokens", "here"]
        )
    )


@pytest.fixture
def mock_message_no_logprobs() -> ChatCompletionMessage:
    """Create a mock message without logprobs."""
    return ChatCompletionMessage(
        role="assistant",
        content=None,
        function_call=None,
        tool_calls=None,
        logprobs=None
    )


@pytest.fixture
def good_lint_results() -> Dict[str, Any]:
    """Create lint results indicating good code quality."""
    return {
        "error_count": 0,
        "warning_count": 1,
        "maintainability_index": 85
    }


@pytest.fixture
def bad_lint_results() -> Dict[str, Any]:
    """Create lint results indicating poor code quality."""
    return {
        "error_count": 3,
        "warning_count": 5,
        "maintainability_index": 45
    }


@pytest.fixture
def good_test_results() -> Dict[str, Any]:
    """Create test results indicating good test coverage and passing tests."""
    return {
        "coverage_percent": 95,
        "tests_passed": 48,
        "total_tests": 50
    }


@pytest.fixture
def bad_test_results() -> Dict[str, Any]:
    """Create test results indicating poor test coverage and failing tests."""
    return {
        "coverage_percent": 45,
        "tests_passed": 15,
        "total_tests": 30
    }


def test_calculate_confidence_high(
    mock_message_with_logprobs: ChatCompletionMessage,
    good_lint_results: Dict[str, Any],
    good_test_results: Dict[str, Any],
) -> None:
    """Test confidence calculation with good metrics."""
    confidence = calculate_confidence(
        mock_message_with_logprobs,
        good_lint_results,
        good_test_results
    )
    assert confidence > 0.8  # Should be high confidence


def test_calculate_confidence_low(
    mock_message_with_logprobs: ChatCompletionMessage,
    bad_lint_results: Dict[str, Any],
    bad_test_results: Dict[str, Any],
) -> None:
    """Test confidence calculation with poor metrics."""
    confidence = calculate_confidence(
        mock_message_with_logprobs,
        bad_lint_results,
        bad_test_results
    )
    assert confidence < 0.6  # Should be low confidence


def test_calculate_llm_score_with_logprobs(
    mock_message_with_logprobs: ChatCompletionMessage
) -> None:
    """Test LLM score calculation with logprobs."""
    score = _calculate_llm_score(mock_message_with_logprobs)
    assert 0.7 < score <= 1.0  # Should be high confidence


def test_calculate_llm_score_no_logprobs(
    mock_message_no_logprobs: ChatCompletionMessage
) -> None:
    """Test LLM score calculation without logprobs."""
    score = _calculate_llm_score(mock_message_no_logprobs)
    assert score == 0.7  # Should return default moderate confidence


def test_calculate_lint_score_good(good_lint_results: Dict[str, Any]) -> None:
    """Test lint score calculation with good metrics."""
    score = _calculate_lint_score(good_lint_results)
    assert score > 0.8  # Should be high confidence


def test_calculate_lint_score_bad(bad_lint_results: Dict[str, Any]) -> None:
    """Test lint score calculation with poor metrics."""
    score = _calculate_lint_score(bad_lint_results)
    assert score < 0.5  # Should be low confidence


def test_calculate_test_score_good(good_test_results: Dict[str, Any]) -> None:
    """Test test score calculation with good metrics."""
    score = _calculate_test_score(good_test_results)
    assert score > 0.8  # Should be high confidence


def test_calculate_test_score_bad(bad_test_results: Dict[str, Any]) -> None:
    """Test test score calculation with poor metrics."""
    score = _calculate_test_score(bad_test_results)
    assert score < 0.5  # Should be low confidence


def test_calculate_test_score_no_tests() -> None:
    """Test test score calculation with no tests."""
    score = _calculate_test_score({"total_tests": 0})
    assert score == 0  # Should be zero confidence 