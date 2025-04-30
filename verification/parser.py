from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET

from crawler.baseline import parse_junit_xml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Exception raised when verification parsing fails."""
    pass


def parse_verification_results(
    before_xml: Path,
    after_xml: Path,
) -> Dict[str, Any]:
    """Parse JUnit XML results from before and after a change.
    
    Args:
        before_xml: Path to JUnit XML results from before the change
        after_xml: Path to JUnit XML results from after the change
        
    Returns:
        Dictionary containing verification metrics:
        {
            "passed_before": bool,  # True if no failures or errors
            "passed_after": bool,   # True if no failures or errors
            "tests_before": {
                "total": int,
                "passed": int,
                "failed": int,
                "skipped": int
            },
            "tests_after": {
                "total": int,
                "passed": int,
                "failed": int,
                "skipped": int
            },
            "regressions": List[str],  # Tests that passed before but failed after
            "fixes": List[str],        # Tests that failed before but passed after
            "new_failures": List[str]  # New tests that failed
        }
        
    Raises:
        VerificationError: If parsing fails
    """
    try:
        # Parse before and after results
        before_results = parse_junit_xml(before_xml)
        after_results = parse_junit_xml(after_xml)
        
        # Extract test case results
        before_cases = {
            f"{case['classname']}.{case['name']}": case["status"]
            for case in before_results["test_cases"]
        }
        after_cases = {
            f"{case['classname']}.{case['name']}": case["status"]
            for case in after_results["test_cases"]
        }
        
        # Find regressions (passed → failed)
        regressions = [
            test_id for test_id, status in after_cases.items()
            if test_id in before_cases
            and before_cases[test_id] == "passed"
            and status == "failed"
        ]
        
        # Find fixes (failed → passed)
        fixes = [
            test_id for test_id, status in after_cases.items()
            if test_id in before_cases
            and before_cases[test_id] == "failed"
            and status == "passed"
        ]
        
        # Find new failures
        new_failures = [
            test_id for test_id, status in after_cases.items()
            if test_id not in before_cases and status == "failed"
        ]
        
        return {
            "passed_before": before_results["tests_failures"] == 0 and before_results["tests_errors"] == 0,
            "passed_after": after_results["tests_failures"] == 0 and after_results["tests_errors"] == 0,
            "tests_before": {
                "total": before_results["tests_total"],
                "passed": before_results["tests_passed"],
                "failed": before_results["tests_failures"],
                "skipped": before_results["tests_skipped"]
            },
            "tests_after": {
                "total": after_results["tests_total"],
                "passed": after_results["tests_passed"],
                "failed": after_results["tests_failures"],
                "skipped": after_results["tests_skipped"]
            },
            "regressions": sorted(regressions),
            "fixes": sorted(fixes),
            "new_failures": sorted(new_failures)
        }
        
    except Exception as e:
        raise VerificationError(f"Failed to parse verification results: {str(e)}") 