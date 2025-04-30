from __future__ import annotations

import json
import pytest
from pathlib import Path
from verification.coverage_check import (
    load_baseline_coverage,
    check_coverage_diff,
)

@pytest.fixture
def baseline_coverage():
    return {
        "line_coverage_percent": 92.5,
        "packages": [
            {"name": "crawler", "line_coverage_percent": 95.0},
            {"name": "engine", "line_coverage_percent": 90.0},
        ]
    }

@pytest.fixture
def current_coverage():
    return {
        "line_coverage_percent": 93.0,
        "packages": [
            {"name": "crawler", "line_coverage_percent": 94.0},
            {"name": "engine", "line_coverage_percent": 92.0},
        ]
    }

def test_load_baseline_coverage(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    baseline_data = {"line_coverage_percent": 90.0}
    
    with open(baseline_file, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f)
    
    loaded = load_baseline_coverage(baseline_file)
    assert loaded == baseline_data

def test_load_baseline_coverage_missing_file():
    with pytest.raises(FileNotFoundError):
        load_baseline_coverage(Path("nonexistent.json"))

def test_check_coverage_diff_pass(baseline_coverage, current_coverage):
    passed, message = check_coverage_diff(current_coverage, baseline_coverage)
    assert passed
    assert "✅ Coverage checks passed" in message
    assert "93.0%" in message
    assert "+0.5%" in message

def test_check_coverage_diff_below_minimum(baseline_coverage):
    current = {**baseline_coverage, "line_coverage_percent": 85.0}
    passed, message = check_coverage_diff(current, baseline_coverage)
    assert not passed
    assert "❌ Coverage below minimum required" in message
    assert "85.0%" in message

def test_check_coverage_diff_excessive_decrease(baseline_coverage):
    current = {**baseline_coverage, "line_coverage_percent": 91.5}
    passed, message = check_coverage_diff(
        current,
        baseline_coverage,
        max_decrease=0.5
    )
    assert not passed
    assert "❌ Coverage decrease" in message
    assert "91.5%" in message

def test_check_coverage_diff_package_changes(baseline_coverage, current_coverage):
    # Modify package coverage to trigger significant change reporting
    current_coverage["packages"][0]["line_coverage_percent"] = 97.0  # +2% change
    
    passed, message = check_coverage_diff(current_coverage, baseline_coverage)
    assert passed
    assert "Significant package changes:" in message
    assert "crawler: 97.0% (+2.0%)" in message

def test_check_coverage_diff_no_packages():
    baseline = {"line_coverage_percent": 92.5}
    current = {"line_coverage_percent": 93.0}
    
    passed, message = check_coverage_diff(current, baseline)
    assert passed
    assert "Significant package changes:" not in message 