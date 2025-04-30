"""Confidence scoring for plan items based on multiple heuristics."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)


def calculate_confidence(
    message: ChatCompletionMessage,
    lint_results: Dict[str, Any],
    test_results: Dict[str, Any],
) -> float:
    """Calculate a confidence score between 0 and 1 for a plan item.
    
    The score is based on:
    1. LLM confidence (from token probabilities)
    2. Static analysis results (linting score)
    3. Test coverage and pass rate
    
    Args:
        message: OpenAI chat completion message with logprobs
        lint_results: Dictionary containing static analysis results:
                     - error_count: Number of linting errors
                     - warning_count: Number of linting warnings
                     - maintainability_index: Code maintainability score (0-100)
        test_results: Dictionary containing test execution results:
                     - coverage_percent: Test coverage percentage
                     - tests_passed: Number of passing tests
                     - total_tests: Total number of tests
    
    Returns:
        Float between 0 and 1 representing confidence in the plan item
    """
    # Calculate individual scores
    llm_score = _calculate_llm_score(message)
    lint_score = _calculate_lint_score(lint_results)
    test_score = _calculate_test_score(test_results)
    
    # Weighted combination of scores
    # We weight LLM confidence highest since it's most directly related to the change
    weights = {
        "llm": 0.5,      # LLM confidence is primary indicator
        "lint": 0.3,     # Static analysis provides good signal
        "test": 0.2      # Test results are important but may be noisy
    }
    
    final_score = (
        weights["llm"] * llm_score +
        weights["lint"] * lint_score +
        weights["test"] * test_score
    )
    
    logger.debug(
        "Calculated confidence score",
        extra={
            "llm_score": llm_score,
            "lint_score": lint_score,
            "test_score": test_score,
            "final_score": final_score
        }
    )
    
    return float(np.clip(final_score, 0, 1))


def _calculate_llm_score(message: ChatCompletionMessage) -> float:
    """Calculate confidence score from LLM token probabilities.
    
    Args:
        message: OpenAI chat completion message with logprobs
    
    Returns:
        Float between 0 and 1 representing LLM confidence
    """
    # If logprobs not available, use moderate confidence
    if not hasattr(message, "logprobs") or not message.logprobs:
        return 0.7
    
    # Extract token probabilities
    token_probs = [
        np.exp(logprob) for logprob in message.logprobs.token_logprobs
        if logprob is not None
    ]
    
    if not token_probs:
        return 0.7
    
    # Use mean probability as base score
    mean_prob = float(np.mean(token_probs))
    
    # Adjust score based on probability distribution
    std_dev = float(np.std(token_probs))
    consistency_penalty = std_dev * 0.1  # Penalize high variance
    
    return np.clip(mean_prob - consistency_penalty, 0, 1)


def _calculate_lint_score(lint_results: Dict[str, Any]) -> float:
    """Calculate confidence score from static analysis results.
    
    Args:
        lint_results: Dictionary containing static analysis metrics
    
    Returns:
        Float between 0 and 1 representing lint-based confidence
    """
    error_count = lint_results.get("error_count", 0)
    warning_count = lint_results.get("warning_count", 0)
    maintainability = lint_results.get("maintainability_index", 50)  # Default to medium
    
    # Heavily penalize errors, moderately penalize warnings
    issue_penalty = (error_count * 0.2) + (warning_count * 0.05)
    
    # Normalize maintainability index to 0-1 range
    maintainability_score = maintainability / 100
    
    # Combine scores with penalty
    return np.clip(maintainability_score - issue_penalty, 0, 1)


def _calculate_test_score(test_results: Dict[str, Any]) -> float:
    """Calculate confidence score from test execution results.
    
    Args:
        test_results: Dictionary containing test metrics
    
    Returns:
        Float between 0 and 1 representing test-based confidence
    """
    coverage = test_results.get("coverage_percent", 0) / 100
    
    # Calculate test pass rate
    total_tests = test_results.get("total_tests", 0)
    if total_tests == 0:
        pass_rate = 0
    else:
        tests_passed = test_results.get("tests_passed", 0)
        pass_rate = tests_passed / total_tests
    
    # Combine coverage and pass rate
    # We weight pass rate higher since failing tests are more critical
    return float(np.clip((0.4 * coverage) + (0.6 * pass_rate), 0, 1)) 