"""Baseline metrics collector for Python projects."""
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class BaselineMetricsError(Exception):
    """Exception raised when there's an error collecting baseline metrics."""

    pass


def run_pytest(
    repo_path: Union[str, Path],
    pytest_args: Optional[List[str]] = None,
    xml_output: str = "results.xml",
) -> Tuple[subprocess.CompletedProcess, Path]:
    """Run pytest with coverage and generate XML reports.

    Args:
        repo_path: Path to the repository
        pytest_args: Additional arguments to pass to pytest
        xml_output: Path to the JUnit XML output file

    Returns:
        Tuple of (CompletedProcess with the pytest result, Path to the XML output file)

    Raises:
        BaselineMetricsError: If the repository path doesn't exist
    """
    repo_path = Path(repo_path)
    if not repo_path.exists() or not repo_path.is_dir():
        raise BaselineMetricsError(f"Repository path does not exist: {repo_path}")

    # Build the pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--cov",
        "--cov-report=xml",
        f"--junitxml={xml_output}",
    ]

    # Add any additional pytest arguments
    if pytest_args:
        cmd.extend(pytest_args)

    logger.info(f"Running pytest in {repo_path}")
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        # Run pytest
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

        xml_path = repo_path / xml_output
        return result, xml_path
    except subprocess.SubprocessError as e:
        raise BaselineMetricsError(f"Failed to run pytest: {str(e)}")


def parse_junit_xml(xml_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse JUnit XML results file.

    Args:
        xml_path: Path to JUnit XML file

    Returns:
        Dictionary with test metrics

    Raises:
        BaselineMetricsError: If the XML file is missing or cannot be parsed
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise BaselineMetricsError(f"JUnit XML file does not exist: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extract test summary
        tests_total = int(root.attrib.get("tests", 0))
        tests_failures = int(root.attrib.get("failures", 0))
        tests_errors = int(root.attrib.get("errors", 0))
        tests_skipped = int(root.attrib.get("skipped", 0))
        tests_passed = tests_total - tests_failures - tests_errors - tests_skipped

        # Calculate success rate
        success_rate = (tests_passed / tests_total) * 100 if tests_total > 0 else 0

        # Extract test cases
        test_cases = []
        for test_case in root.findall(".//testcase"):
            case_info = {
                "name": test_case.attrib.get("name", ""),
                "classname": test_case.attrib.get("classname", ""),
                "time": float(test_case.attrib.get("time", 0)),
                "status": "passed",
            }

            # Check for failures or errors
            failure = test_case.find("failure")
            error = test_case.find("error")
            skipped = test_case.find("skipped")

            if failure is not None:
                case_info["status"] = "failed"
                case_info["message"] = failure.attrib.get("message", "")
            elif error is not None:
                case_info["status"] = "error"
                case_info["message"] = error.attrib.get("message", "")
            elif skipped is not None:
                case_info["status"] = "skipped"
                case_info["message"] = skipped.attrib.get("message", "")

            test_cases.append(case_info)

        return {
            "tests_total": tests_total,
            "tests_passed": tests_passed,
            "tests_failures": tests_failures,
            "tests_errors": tests_errors,
            "tests_skipped": tests_skipped,
            "success_rate": success_rate,
            "test_cases": test_cases,
        }
    except Exception as e:
        raise BaselineMetricsError(f"Failed to parse JUnit XML: {str(e)}")


def parse_coverage_xml(coverage_xml_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse coverage XML file.

    Args:
        coverage_xml_path: Path to coverage.xml file

    Returns:
        Dictionary with coverage metrics

    Raises:
        BaselineMetricsError: If the coverage file is missing or cannot be parsed
    """
    coverage_xml_path = Path(coverage_xml_path)
    if not coverage_xml_path.exists():
        raise BaselineMetricsError(f"Coverage XML file does not exist: {coverage_xml_path}")

    try:
        tree = ET.parse(coverage_xml_path)
        root = tree.getroot()

        # Extract overall coverage
        coverage_element = root.find(".//*[@line-rate]")
        if coverage_element is None:
            raise BaselineMetricsError("Could not find coverage information in XML")

        line_rate = float(coverage_element.attrib.get("line-rate", 0))
        branch_rate = float(coverage_element.attrib.get("branch-rate", 0))
        
        # Convert to percentages
        line_percent = line_rate * 100
        branch_percent = branch_rate * 100

        # Extract package and file-level coverage
        packages = []
        for package in root.findall(".//package"):
            package_name = package.attrib.get("name", "")
            package_line_rate = float(package.attrib.get("line-rate", 0)) * 100
            
            files = []
            for file_elem in package.findall("./classes/class"):
                file_name = file_elem.attrib.get("filename", "")
                file_line_rate = float(file_elem.attrib.get("line-rate", 0)) * 100
                
                files.append({
                    "name": file_name,
                    "line_coverage_percent": file_line_rate,
                })
            
            packages.append({
                "name": package_name,
                "line_coverage_percent": package_line_rate,
                "files": files,
            })

        return {
            "line_coverage_percent": line_percent,
            "branch_coverage_percent": branch_percent,
            "packages": packages,
        }
    except Exception as e:
        raise BaselineMetricsError(f"Failed to parse coverage XML: {str(e)}")


def collect_baseline_metrics(
    repo_path: Union[str, Path], 
    pytest_args: Optional[List[str]] = None,
    xml_output: str = "results.xml",
) -> Dict[str, Any]:
    """Collect baseline metrics for a Python repository.

    Args:
        repo_path: Path to the repository
        pytest_args: Additional arguments to pass to pytest
        xml_output: Path to the JUnit XML output file

    Returns:
        Dictionary with test and coverage metrics

    Raises:
        BaselineMetricsError: If metrics collection fails
    """
    repo_path = Path(repo_path)
    
    # Run pytest
    result, xml_path = run_pytest(repo_path, pytest_args, xml_output)
    
    # Determine if tests passed overall
    tests_passed_overall = result.returncode == 0
    
    try:
        # Parse test results
        test_metrics = parse_junit_xml(xml_path)
        
        # Parse coverage results
        coverage_xml_path = repo_path / "coverage.xml"
        coverage_metrics = parse_coverage_xml(coverage_xml_path)
        
        # Combine metrics
        metrics = {
            "overall_success": tests_passed_overall,
            "tests": test_metrics,
            "coverage": coverage_metrics,
        }
        
        return metrics
    except BaselineMetricsError as e:
        # If parsing fails but we have the pytest output, we can try to extract basic metrics
        logger.warning(f"Failed to parse XML reports: {e}. Falling back to output parsing.")
        return parse_pytest_output(result.stdout, result.stderr, tests_passed_overall)


def parse_pytest_output(stdout: str, stderr: str, tests_passed_overall: bool) -> Dict[str, Any]:
    """Parse pytest output to extract basic metrics when XML parsing fails.

    Args:
        stdout: Standard output from pytest
        stderr: Standard error from pytest
        tests_passed_overall: Whether the tests passed overall

    Returns:
        Dictionary with basic test and coverage metrics
    """
    # Extract test summary using regex
    tests_summary_match = re.search(
        r"=+ ([\d]+) passed, ([\d]+) failed, ([\d]+) skipped", 
        stdout
    )
    
    tests_passed = 0
    tests_failed = 0
    tests_skipped = 0
    
    if tests_summary_match:
        tests_passed = int(tests_summary_match.group(1))
        tests_failed = int(tests_summary_match.group(2))
        tests_skipped = int(tests_summary_match.group(3))
    
    # Extract coverage using regex
    coverage_match = re.search(r"TOTAL\s+[\d]+\s+[\d]+\s+([\d]+)%", stdout)
    coverage_percent = 0
    
    if coverage_match:
        coverage_percent = float(coverage_match.group(1))
    
    return {
        "overall_success": tests_passed_overall,
        "tests": {
            "tests_total": tests_passed + tests_failed + tests_skipped,
            "tests_passed": tests_passed,
            "tests_failures": tests_failed,
            "tests_skipped": tests_skipped,
            "success_rate": (tests_passed / (tests_passed + tests_failed + tests_skipped)) * 100 
                if (tests_passed + tests_failed + tests_skipped) > 0 else 0,
        },
        "coverage": {
            "line_coverage_percent": coverage_percent,
            "branch_coverage_percent": 0,  # Can't extract this from console output
        }
    }


def save_metrics_to_json(metrics: Dict[str, Any], output_path: Union[str, Path]) -> None:
    """Save metrics to a JSON file.

    Args:
        metrics: The metrics to save
        output_path: Path to the output JSON file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"Metrics saved to {output_path}")


def main() -> int:
    """Run the baseline metrics collector from the command line.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect baseline metrics for a Python repository")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("-o", "--output", default="baseline_metrics.json", 
                        help="Path to the output JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--pytest-args", nargs="*", help="Additional arguments to pass to pytest")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    try:
        metrics = collect_baseline_metrics(args.repo_path, args.pytest_args)
        save_metrics_to_json(metrics, args.output)
        
        # Print a summary
        print(f"\nTests: {metrics['tests']['tests_passed']}/{metrics['tests']['tests_total']} passed "
              f"({metrics['tests']['success_rate']:.1f}%)")
        print(f"Coverage: {metrics['coverage']['line_coverage_percent']:.1f}%")
        
        return 0
    except BaselineMetricsError as e:
        logger.error(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main()) 