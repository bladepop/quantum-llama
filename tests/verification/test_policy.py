"""Tests for the merge-gate policy."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from models.plan_item import PlanItem
from verification.policy import MergeGatePolicy, PolicyCheckResult


@pytest.fixture
def before_junit_xml(tmp_path):
    """Create a sample JUnit XML file for before state."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="3" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_will_pass" time="0.01">
      <failure message="test failure">AssertionError: expected True but got False</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_stable" time="0.01"/>
  </testsuite>
</testsuites>
"""
    xml_file = tmp_path / "before.xml"
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def after_junit_xml(tmp_path):
    """Create a sample JUnit XML file for after state with changes."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="3" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_will_pass" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_stable" time="0.01"/>
  </testsuite>
</testsuites>
"""
    xml_file = tmp_path / "after.xml"
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def failing_after_junit_xml(tmp_path):
    """Create a sample JUnit XML file for after state with failures."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="2" skipped="0" tests="3" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01">
      <failure message="test failure">AssertionError: regression</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_will_pass" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_stable" time="0.01">
      <failure message="test failure">AssertionError: another regression</failure>
    </testcase>
  </testsuite>
</testsuites>
"""
    xml_file = tmp_path / "after_failing.xml"
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def plan_item_high_confidence():
    """Create a plan item with confidence above threshold."""
    return PlanItem(
        id="test-id",
        file_path="test.py",
        action="MODIFY",
        reason="Test change",
        confidence=0.9
    )


@pytest.fixture
def plan_item_low_confidence():
    """Create a plan item with confidence below threshold."""
    return PlanItem(
        id="test-id",
        file_path="test.py",
        action="MODIFY",
        reason="Test change",
        confidence=0.7
    )


async def test_check_test_results_passing(before_junit_xml, after_junit_xml):
    """Test checking test results when all tests pass after change."""
    policy = MergeGatePolicy()
    result = await policy.check_test_results(before_junit_xml, after_junit_xml)
    
    assert result.passed is True
    assert "Tests after change: 3/3 passed" in result.summary
    assert "Fixes (1):" in result.summary
    assert "test_module.TestClass.test_will_pass" in result.summary


async def test_check_test_results_failing(before_junit_xml, failing_after_junit_xml):
    """Test checking test results when tests fail after change."""
    policy = MergeGatePolicy()
    result = await policy.check_test_results(before_junit_xml, failing_after_junit_xml)
    
    assert result.passed is False
    assert "Tests after change: 1/3 passed" in result.summary
    assert "Regressions (2):" in result.summary
    assert "test_module.TestClass.test_success" in result.summary
    assert "test_module.TestClass.test_stable" in result.summary


def test_check_confidence_passing(plan_item_high_confidence):
    """Test checking confidence when above threshold."""
    policy = MergeGatePolicy()
    result = policy.check_confidence(plan_item_high_confidence)
    
    assert result.passed is True
    assert "Plan confidence: 90.00%" in result.summary
    assert result.details["confidence"] == 0.9


def test_check_confidence_failing(plan_item_low_confidence):
    """Test checking confidence when below threshold."""
    policy = MergeGatePolicy()
    result = policy.check_confidence(plan_item_low_confidence)
    
    assert result.passed is False
    assert "Plan confidence: 70.00%" in result.summary
    assert result.details["confidence"] == 0.7


async def test_post_check():
    """Test posting check results to GitHub."""
    policy = MergeGatePolicy(github_token="test-token")
    check_result = PolicyCheckResult(
        passed=True,
        title="Test Check",
        summary="Test summary"
    )
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.raise_for_status = AsyncMock()
        
        await policy.post_check(
            repo_owner="owner",
            repo_name="repo",
            sha="test-sha",
            check_result=check_result
        )
        
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "token test-token"
        assert call_kwargs["json"]["conclusion"] == "success"


async def test_evaluate_pr_passing(
    before_junit_xml, after_junit_xml, plan_item_high_confidence
):
    """Test PR evaluation when all checks pass."""
    policy = MergeGatePolicy(github_token="test-token")
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.raise_for_status = AsyncMock()
        
        result = await policy.evaluate_pr(
            before_xml=before_junit_xml,
            after_xml=after_junit_xml,
            plan_item=plan_item_high_confidence,
            repo_owner="owner",
            repo_name="repo",
            sha="test-sha"
        )
        
        assert result is True
        assert mock_post.call_count == 2  # One call for each check


async def test_evaluate_pr_failing_tests(
    before_junit_xml, failing_after_junit_xml, plan_item_high_confidence
):
    """Test PR evaluation when tests fail."""
    policy = MergeGatePolicy(github_token="test-token")
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.raise_for_status = AsyncMock()
        
        result = await policy.evaluate_pr(
            before_xml=before_junit_xml,
            after_xml=failing_after_junit_xml,
            plan_item=plan_item_high_confidence,
            repo_owner="owner",
            repo_name="repo",
            sha="test-sha"
        )
        
        assert result is False


async def test_evaluate_pr_failing_confidence(
    before_junit_xml, after_junit_xml, plan_item_low_confidence
):
    """Test PR evaluation when confidence is too low."""
    policy = MergeGatePolicy(github_token="test-token")
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.raise_for_status = AsyncMock()
        
        result = await policy.evaluate_pr(
            before_xml=before_junit_xml,
            after_xml=after_junit_xml,
            plan_item=plan_item_low_confidence,
            repo_owner="owner",
            repo_name="repo",
            sha="test-sha"
        )
        
        assert result is False 