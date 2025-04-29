"""Tests for the snapshot_db module."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from crawler import snapshot_db


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database path for testing."""
    return tmp_path / "test.db"


@pytest.fixture
def sample_metrics():
    """Create sample metrics data for testing."""
    return {
        "overall_success": True,
        "tests": {
            "tests_total": 50,
            "tests_passed": 45,
            "tests_failures": 3,
            "tests_skipped": 2,
            "success_rate": 90.0,
            "test_cases": []
        },
        "coverage": {
            "line_coverage_percent": 85.5,
            "branch_coverage_percent": 80.0,
            "packages": [
                {
                    "name": "crawler",
                    "line_coverage_percent": 90.5,
                    "files": [
                        {"name": "baseline.py", "line_coverage_percent": 95.0},
                        {"name": "snapshot_db.py", "line_coverage_percent": 86.0}
                    ]
                },
                {
                    "name": "planner",
                    "line_coverage_percent": 80.5,
                    "files": [
                        {"name": "plan.py", "line_coverage_percent": 80.5}
                    ]
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_init_db(test_db_path):
    """Test database initialization."""
    conn = await snapshot_db.init_db(test_db_path)
    assert os.path.exists(test_db_path)
    
    # Verify tables were created
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in await cursor.fetchall()]
    
    assert "runs" in tables
    assert "files" in tables
    assert "packages" in tables
    
    await conn.close()


@pytest.mark.asyncio
async def test_store_snapshot(test_db_path, sample_metrics):
    """Test storing a snapshot in the database."""
    repo_path = "/path/to/repo"
    run_id = await snapshot_db.store_snapshot(test_db_path, sample_metrics, repo_path)
    
    # Verify UUID format
    uuid.UUID(run_id)  # Will raise ValueError if not valid UUID
    
    # Verify data was stored
    conn = await snapshot_db.init_db(test_db_path)
    conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    }
    
    # Check runs table
    cursor = await conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
    run = await cursor.fetchone()
    
    assert run is not None
    assert run["repo_path"] == repo_path
    assert run["overall_success"] == 1  # SQLite stores booleans as integers
    assert run["tests_total"] == 50
    assert run["tests_passed"] == 45
    assert run["line_coverage_percent"] == 85.5
    
    # Check packages table
    cursor = await conn.execute("SELECT * FROM packages WHERE run_id = ?", (run_id,))
    packages = await cursor.fetchall()
    
    assert len(packages) == 2
    package_names = [p["package_name"] for p in packages]
    assert "crawler" in package_names
    assert "planner" in package_names
    
    # Check files table
    cursor = await conn.execute("SELECT * FROM files WHERE run_id = ?", (run_id,))
    files = await cursor.fetchall()
    
    assert len(files) == 3
    file_names = [f["file_name"] for f in files]
    assert "baseline.py" in file_names
    assert "snapshot_db.py" in file_names
    assert "plan.py" in file_names
    
    await conn.close()


@pytest.mark.asyncio
async def test_get_run(test_db_path, sample_metrics):
    """Test retrieving a run from the database."""
    repo_path = "/path/to/repo"
    run_id = await snapshot_db.store_snapshot(test_db_path, sample_metrics, repo_path)
    
    # Retrieve the run
    run = await snapshot_db.get_run(test_db_path, run_id)
    
    # Verify run data
    assert run["id"] == run_id
    assert run["repo_path"] == repo_path
    assert run["overall_success"] is True  # Converted back to boolean
    assert run["tests_total"] == 50
    assert run["tests_passed"] == 45
    assert run["line_coverage_percent"] == 85.5
    
    # Verify packages structure
    assert "packages" in run
    assert "crawler" in run["packages"]
    assert "planner" in run["packages"]
    
    # Verify package details
    crawler_pkg = run["packages"]["crawler"]
    assert crawler_pkg["line_coverage_percent"] == 90.5
    assert len(crawler_pkg["files"]) == 2
    
    # Verify file data is organized by package
    file_names = [f["file_name"] for f in crawler_pkg["files"]]
    assert "baseline.py" in file_names
    assert "snapshot_db.py" in file_names


@pytest.mark.asyncio
async def test_list_runs(test_db_path, sample_metrics):
    """Test listing runs from the database."""
    # Create multiple runs
    for i in range(5):
        repo_path = f"/path/to/repo{i}"
        await snapshot_db.store_snapshot(test_db_path, sample_metrics, repo_path)
    
    # List runs with limit
    runs = await snapshot_db.list_runs(test_db_path, limit=3)
    
    # Verify correct number of runs returned
    assert len(runs) == 3
    
    # Verify runs are sorted by timestamp (newest first)
    for i in range(len(runs) - 1):
        assert runs[i]["timestamp"] >= runs[i + 1]["timestamp"]
    
    # Verify basic fields are present
    for run in runs:
        assert "id" in run
        assert "repo_path" in run
        assert "timestamp" in run
        assert "overall_success" in run
        assert "tests_total" in run
        assert "tests_passed" in run
        assert "success_rate" in run
        assert "line_coverage_percent" in run


@pytest.mark.asyncio
async def test_get_runs_count(test_db_path, sample_metrics):
    """Test counting runs in the database."""
    # Create multiple runs
    for i in range(7):
        repo_path = f"/path/to/repo{i}"
        await snapshot_db.store_snapshot(test_db_path, sample_metrics, repo_path)
    
    # Count runs
    count = await snapshot_db.get_runs_count(test_db_path)
    
    # Verify count
    assert count == 7


@pytest.mark.asyncio
async def test_error_handling(test_db_path):
    """Test error handling in the snapshot_db module."""
    # Test with invalid run ID
    with pytest.raises(snapshot_db.SnapshotDBError):
        await snapshot_db.get_run(test_db_path, "non-existent-id")
    
    # Test with invalid database path
    with pytest.raises(snapshot_db.SnapshotDBError):
        await snapshot_db.init_db("/path/that/does/not/exist/db.sqlite")
    
    # Test with invalid metrics
    with pytest.raises(snapshot_db.SnapshotDBError):
        await snapshot_db.store_snapshot(test_db_path, {}, "/path/to/repo") 