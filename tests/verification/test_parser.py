from __future__ import annotations

import pytest
from pathlib import Path

from verification.parser import parse_verification_results, VerificationError


@pytest.fixture
def before_junit_xml(tmp_path):
    """Create a sample JUnit XML file for before state."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="2" skipped="1" tests="4" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_failure" time="0.01">
      <failure message="test failure">AssertionError: expected True but got False</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_will_pass" time="0.01">
      <failure message="test failure">AssertionError: expected True but got False</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_skipped" time="0.01">
      <skipped message="skipping this test"/>
    </testcase>
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
  <testsuite name="pytest" errors="0" failures="2" skipped="1" tests="5" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01">
      <failure message="test failure">AssertionError: regression</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_failure" time="0.01">
      <failure message="test failure">AssertionError: still failing</failure>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_will_pass" time="0.01"/>
    <testcase classname="test_module.TestClass" name="test_skipped" time="0.01">
      <skipped message="skipping this test"/>
    </testcase>
    <testcase classname="test_module.TestClass" name="test_new" time="0.01">
      <failure message="test failure">AssertionError: new test failing</failure>
    </testcase>
  </testsuite>
</testsuites>
"""
    xml_file = tmp_path / "after.xml"
    xml_file.write_text(xml_content)
    return xml_file


def test_parse_verification_results(before_junit_xml, after_junit_xml):
    """Test parsing verification results from before/after JUnit XML files."""
    results = parse_verification_results(before_junit_xml, after_junit_xml)
    
    # Check overall pass/fail status
    assert results["passed_before"] is False  # 1 passed out of 3 non-skipped
    assert results["passed_after"] is False   # 1 passed out of 4 non-skipped
    
    # Check before test counts
    assert results["tests_before"]["total"] == 4
    assert results["tests_before"]["passed"] == 1
    assert results["tests_before"]["failed"] == 2
    assert results["tests_before"]["skipped"] == 1
    
    # Check after test counts
    assert results["tests_after"]["total"] == 5
    assert results["tests_after"]["passed"] == 1
    assert results["tests_after"]["failed"] == 3
    assert results["tests_after"]["skipped"] == 1
    
    # Check test status changes
    assert results["regressions"] == ["test_module.TestClass.test_success"]
    assert results["fixes"] == ["test_module.TestClass.test_will_pass"]
    assert results["new_failures"] == ["test_module.TestClass.test_new"]


def test_parse_verification_results_missing_file():
    """Test error handling when XML files don't exist."""
    with pytest.raises(VerificationError) as exc:
        parse_verification_results(
            Path("nonexistent_before.xml"),
            Path("nonexistent_after.xml")
        )
    assert "Failed to parse verification results" in str(exc.value)


def test_parse_verification_results_invalid_xml(tmp_path):
    """Test error handling with invalid XML content."""
    invalid_xml = tmp_path / "invalid.xml"
    invalid_xml.write_text("This is not XML")
    
    valid_xml = tmp_path / "valid.xml"
    valid_xml.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="1" time="0.1">
    <testcase classname="test_module.TestClass" name="test_success" time="0.01"/>
  </testsuite>
</testsuites>
""")
    
    with pytest.raises(VerificationError) as exc:
        parse_verification_results(invalid_xml, valid_xml)
    assert "Failed to parse verification results" in str(exc.value) 