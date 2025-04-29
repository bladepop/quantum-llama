"""Tests for the baseline metrics collector."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from crawler.baseline import (
    BaselineMetricsError,
    run_pytest,
    parse_junit_xml,
    parse_coverage_xml,
    collect_baseline_metrics,
    parse_pytest_output,
    save_metrics_to_json,
)


@pytest.fixture
def sample_junit_xml():
    """Sample JUnit XML content for testing."""
    return """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="5" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_success_2" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_success_3" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_failure" time="0.01">
      <failure message="test failure">AssertionError: expected True but got False</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_skipped" time="0.01">
      <skipped message="skipping this test"/>
    </testcase>
  </testsuite>
</testsuites>
"""


@pytest.fixture
def sample_coverage_xml():
    """Sample coverage XML content for testing."""
    return """<?xml version="1.0" ?>
<coverage version="6.5.0" timestamp="1636451234" lines-valid="100" lines-covered="80" line-rate="0.8" branches-covered="10" branches-valid="20" branch-rate="0.5" complexity="0">
    <packages>
        <package name="crawler" line-rate="0.9" branch-rate="0.7">
            <classes>
                <class name="crawler.py" filename="crawler/crawler.py" line-rate="0.9">
                    <methods/>
                    <lines/>
                </class>
            </classes>
        </package>
        <package name="models" line-rate="0.7" branch-rate="0.4">
            <classes>
                <class name="models.py" filename="models/models.py" line-rate="0.7">
                    <methods/>
                    <lines/>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
"""


@pytest.fixture
def sample_pytest_output():
    """Sample pytest console output for testing."""
    return """============================= test session starts ==============================
platform linux -- Python 3.9.7, pytest-7.0.1, pluggy-1.0.0
rootdir: /home/user/project
plugins: cov-4.0.0
collected 5 items

test_module.py::TestClass::test_success PASSED                             [ 20%]
test_module.py::TestClass::test_success_2 PASSED                           [ 40%]
test_module.py::TestClass::test_success_3 PASSED                           [ 60%]
test_module.py::TestClass::test_failure FAILED                             [ 80%]
test_module.py::TestClass::test_skipped SKIPPED                            [100%]

================================== FAILURES ===================================
__________________________ TestClass.test_failure ___________________________

    def test_failure(self):
>       assert False
E       assert False

test_module.py:25: AssertionError
======================= short test summary info ============================
FAILED test_module.py::TestClass::test_failure
================== 1 failed, 3 passed, 1 skipped in 0.10s ==================

----------- coverage: platform linux, python 3.9.7-final-0 -----------
Name                  Stmts   Miss  Cover
-----------------------------------------
crawler/crawler.py      100     10    90%
models/models.py         50     15    70%
-----------------------------------------
TOTAL                   150     25    83%
"""


def test_parse_junit_xml(sample_junit_xml, tmp_path):
    """Test parsing JUnit XML."""
    xml_file = tmp_path / "results.xml"
    xml_file.write_text(sample_junit_xml)
    
    results = parse_junit_xml(xml_file)
    
    assert results["tests_total"] == 5
    assert results["tests_passed"] == 3
    assert results["tests_failures"] == 1
    assert results["tests_skipped"] == 1
    assert results["success_rate"] == 60.0
    assert len(results["test_cases"]) == 5
    
    # Check test case details
    assert results["test_cases"][0]["status"] == "passed"
    assert results["test_cases"][3]["status"] == "failed"
    assert results["test_cases"][4]["status"] == "skipped"


def test_parse_coverage_xml(sample_coverage_xml, tmp_path):
    """Test parsing coverage XML."""
    xml_file = tmp_path / "coverage.xml"
    xml_file.write_text(sample_coverage_xml)
    
    results = parse_coverage_xml(xml_file)
    
    assert results["line_coverage_percent"] == 80.0
    assert results["branch_coverage_percent"] == 50.0
    
    # Check package details
    assert len(results["packages"]) == 2
    assert results["packages"][0]["name"] == "crawler"
    assert results["packages"][0]["line_coverage_percent"] == 90.0
    assert results["packages"][1]["name"] == "models"
    assert results["packages"][1]["line_coverage_percent"] == 70.0
    
    # Check file details
    assert results["packages"][0]["files"][0]["name"] == "crawler/crawler.py"
    assert results["packages"][0]["files"][0]["line_coverage_percent"] == 90.0


def test_parse_pytest_output(sample_pytest_output):
    """Test parsing pytest console output."""
    results = parse_pytest_output(sample_pytest_output, "", True)
    
    assert results["overall_success"] is True
    assert results["tests"]["tests_total"] == 5
    assert results["tests"]["tests_passed"] == 3
    assert results["tests"]["tests_failures"] == 1
    assert results["tests"]["tests_skipped"] == 1
    assert results["tests"]["success_rate"] == 60.0
    assert results["coverage"]["line_coverage_percent"] == 83.0


def test_run_pytest():
    """Test running pytest."""
    with patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_dir", return_value=True):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output"
        mock_run.return_value = mock_result
        
        result, xml_path = run_pytest("/fake/repo")
        
        # Check the pytest command
        args, kwargs = mock_run.call_args
        assert "pytest" in args[0]
        assert "--cov" in args[0]
        assert "--junitxml" in args[0]
        assert kwargs["cwd"] == Path("/fake/repo")
        
        # Check the result
        assert result.returncode == 0
        assert xml_path == Path("/fake/repo/results.xml")


def test_run_pytest_error():
    """Test error handling when running pytest."""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(BaselineMetricsError, match="Repository path does not exist"):
            run_pytest("/nonexistent/repo")
            
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_dir", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.SubprocessError("Command failed")):
        with pytest.raises(BaselineMetricsError, match="Failed to run pytest"):
            run_pytest("/fake/repo")


def test_collect_baseline_metrics():
    """Test collecting baseline metrics."""
    with patch("crawler.baseline.run_pytest") as mock_run_pytest, \
         patch("crawler.baseline.parse_junit_xml") as mock_parse_junit, \
         patch("crawler.baseline.parse_coverage_xml") as mock_parse_coverage:
        # Setup mocks
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run_pytest.return_value = (mock_result, Path("/fake/results.xml"))
        
        mock_parse_junit.return_value = {
            "tests_total": 5,
            "tests_passed": 4,
            "tests_failures": 1,
            "tests_skipped": 0,
            "success_rate": 80.0,
            "test_cases": [],
        }
        
        mock_parse_coverage.return_value = {
            "line_coverage_percent": 90.0,
            "branch_coverage_percent": 85.0,
            "packages": [],
        }
        
        # Call the function
        metrics = collect_baseline_metrics("/fake/repo")
        
        # Check results
        assert metrics["overall_success"] is True
        assert metrics["tests"]["tests_passed"] == 4
        assert metrics["tests"]["tests_total"] == 5
        assert metrics["tests"]["success_rate"] == 80.0
        assert metrics["coverage"]["line_coverage_percent"] == 90.0
        assert metrics["coverage"]["branch_coverage_percent"] == 85.0


def test_collect_baseline_metrics_fallback():
    """Test fallback to output parsing when XML parsing fails."""
    with patch("crawler.baseline.run_pytest") as mock_run_pytest, \
         patch("crawler.baseline.parse_junit_xml", side_effect=BaselineMetricsError("XML error")), \
         patch("crawler.baseline.parse_pytest_output") as mock_parse_output:
        # Setup mocks
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output"
        mock_result.stderr = ""
        mock_run_pytest.return_value = (mock_result, Path("/fake/results.xml"))
        
        mock_parse_output.return_value = {
            "overall_success": True,
            "tests": {
                "tests_total": 5,
                "tests_passed": 4,
                "tests_failures": 1,
                "tests_skipped": 0,
                "success_rate": 80.0,
            },
            "coverage": {
                "line_coverage_percent": 90.0,
                "branch_coverage_percent": 0,
            }
        }
        
        # Call the function
        metrics = collect_baseline_metrics("/fake/repo")
        
        # Check results
        assert metrics["overall_success"] is True
        assert metrics["tests"]["tests_passed"] == 4
        assert metrics["coverage"]["line_coverage_percent"] == 90.0
        
        # Verify fallback was called with correct args
        mock_parse_output.assert_called_once_with("Test output", "", True)


def test_save_metrics_to_json(tmp_path):
    """Test saving metrics to JSON."""
    metrics = {
        "overall_success": True,
        "tests": {
            "tests_total": 10,
            "tests_passed": 9,
        },
        "coverage": {
            "line_coverage_percent": 85.5,
        }
    }
    
    output_file = tmp_path / "metrics.json"
    
    with patch("builtins.open", mock_open()) as mock_file:
        save_metrics_to_json(metrics, output_file)
        mock_file.assert_called_once_with(output_file, 'w', encoding='utf-8')
        handle = mock_file()
        handle.write.assert_called_once()
        
        # Check that it wrote valid JSON
        written_data = handle.write.call_args[0][0]
        parsed_data = json.loads(written_data)
        assert parsed_data == metrics 