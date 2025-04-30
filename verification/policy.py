"""Merge-gate policy for pull requests."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field

from models.plan_item import PlanItem
from verification.parser import parse_verification_results

logger = logging.getLogger(__name__)


class PolicyCheckResult(BaseModel):
    """Result of a policy check."""

    passed: bool = Field(description="Whether the check passed")
    title: str = Field(description="Short title for the check")
    summary: str = Field(description="Detailed summary of the check result")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional check details"
    )


class MergeGatePolicy:
    """Policy enforcer for pull request merge decisions."""

    def __init__(self, github_token: Optional[str] = None) -> None:
        """Initialize the policy enforcer.
        
        Args:
            github_token: GitHub token for API access. If not provided, will try GITHUB_TOKEN env var.
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            logger.warning("No GitHub token provided, check posting will be unavailable")

    async def check_test_results(
        self, before_xml: Path, after_xml: Path
    ) -> PolicyCheckResult:
        """Check test results from before and after the change.
        
        Args:
            before_xml: Path to JUnit XML from before the change
            after_xml: Path to JUnit XML from after the change
            
        Returns:
            PolicyCheckResult with the check outcome
        """
        results = parse_verification_results(before_xml, after_xml)
        
        # Build summary sections
        summary_parts = [
            f"Tests after change: {results['tests_after']['passed']}/{results['tests_after']['total']} passed",
        ]
        
        if results["regressions"]:
            summary_parts.append(f"\nRegressions ({len(results['regressions'])}):")
            for test in results["regressions"]:
                summary_parts.append(f"- {test}")
                
        if results["fixes"]:
            summary_parts.append(f"\nFixes ({len(results['fixes'])}):")
            for test in results["fixes"]:
                summary_parts.append(f"- {test}")
                
        if results["new_failures"]:
            summary_parts.append(f"\nNew failures ({len(results['new_failures'])}):")
            for test in results["new_failures"]:
                summary_parts.append(f"- {test}")
        
        return PolicyCheckResult(
            passed=results["passed_after"],
            title="Test Results",
            summary="\n".join(summary_parts),
            details=results
        )

    def check_confidence(self, plan_item: PlanItem) -> PolicyCheckResult:
        """Check if the plan item's confidence meets the threshold.
        
        Args:
            plan_item: The plan item to check
            
        Returns:
            PolicyCheckResult with the check outcome
        """
        CONFIDENCE_THRESHOLD = 0.8
        
        return PolicyCheckResult(
            passed=plan_item.confidence >= CONFIDENCE_THRESHOLD,
            title="LLM Confidence",
            summary=(
                f"Plan confidence: {plan_item.confidence:.2%}\n"
                f"Required threshold: {CONFIDENCE_THRESHOLD:.2%}\n\n"
                f"Reason for change: {plan_item.reason}"
            ),
            details={"confidence": plan_item.confidence, "threshold": CONFIDENCE_THRESHOLD}
        )

    async def post_check(
        self,
        repo_owner: str,
        repo_name: str,
        sha: str,
        check_result: PolicyCheckResult,
    ) -> None:
        """Post a check result to GitHub.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            sha: Commit SHA to post the check for
            check_result: The check result to post
        """
        if not self.github_token:
            logger.error("Cannot post check: no GitHub token available")
            return
            
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/check-runs"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}",
        }
        
        data = {
            "name": check_result.title,
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success" if check_result.passed else "failure",
            "output": {
                "title": check_result.title,
                "summary": check_result.summary,
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Posted check {check_result.title} for {sha}")

    async def evaluate_pr(
        self,
        before_xml: Path,
        after_xml: Path,
        plan_item: PlanItem,
        repo_owner: str,
        repo_name: str,
        sha: str,
    ) -> bool:
        """Evaluate a PR against all policy checks.
        
        Args:
            before_xml: Path to JUnit XML from before the change
            after_xml: Path to JUnit XML from after the change
            plan_item: The plan item being implemented
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            sha: Commit SHA to post checks for
            
        Returns:
            True if all checks pass, False otherwise
        """
        # Run all checks
        test_result = await self.check_test_results(before_xml, after_xml)
        confidence_result = self.check_confidence(plan_item)
        
        # Post results to GitHub
        await self.post_check(repo_owner, repo_name, sha, test_result)
        await self.post_check(repo_owner, repo_name, sha, confidence_result)
        
        # PR can only be merged if all checks pass
        return test_result.passed and confidence_result.passed 