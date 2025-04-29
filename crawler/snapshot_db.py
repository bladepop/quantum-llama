"""SQLite persistence for snapshot metrics from code repositories.

This module handles the storage and retrieval of repository metrics in a SQLite database.
It uses aiosqlite for async database operations with the following tables:
- runs: Track each analysis run with timestamp and repository info
- files: Store file-level metrics (coverage, lines of code, etc.)
- coverage: Store package and overall coverage metrics
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiosqlite

logger = logging.getLogger(__name__)


class SnapshotDBError(Exception):
    """Exception raised when there's an error with the snapshot database."""

    pass


# SQL statements for creating tables
CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    overall_success INTEGER NOT NULL,
    tests_total INTEGER NOT NULL,
    tests_passed INTEGER NOT NULL,
    tests_failed INTEGER NOT NULL,
    tests_skipped INTEGER NOT NULL,
    success_rate REAL NOT NULL,
    line_coverage_percent REAL NOT NULL,
    branch_coverage_percent REAL NOT NULL,
    metadata TEXT
)
"""

CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    package_name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    line_coverage_percent REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
)
"""

CREATE_PACKAGES_TABLE = """
CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    package_name TEXT NOT NULL,
    line_coverage_percent REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id)
)
"""


async def init_db(db_path: Union[str, Path]) -> aiosqlite.Connection:
    """Initialize the database and create tables if they don't exist.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        An open database connection

    Raises:
        SnapshotDBError: If there's an error initializing the database
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = await aiosqlite.connect(str(db_path))
        
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
        await conn.execute(CREATE_RUNS_TABLE)
        await conn.execute(CREATE_FILES_TABLE)
        await conn.execute(CREATE_PACKAGES_TABLE)
        await conn.commit()
        
        logger.info(f"Initialized database at {db_path}")
        return conn
    except Exception as e:
        raise SnapshotDBError(f"Failed to initialize database: {str(e)}")


async def store_snapshot(
    db_path: Union[str, Path], 
    metrics: Dict[str, Any], 
    repo_path: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Store a snapshot of repository metrics in the database.

    Args:
        db_path: Path to the SQLite database file
        metrics: Dictionary with metrics data (from baseline.collect_baseline_metrics)
        repo_path: Path to the repository
        metadata: Optional additional metadata as a dictionary

    Returns:
        The ID of the run that was stored

    Raises:
        SnapshotDBError: If there's an error storing the snapshot
    """
    conn = await init_db(db_path)
    run_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    try:
        # Extract metrics
        overall_success = metrics.get("overall_success", False)
        test_metrics = metrics.get("tests", {})
        coverage_metrics = metrics.get("coverage", {})
        
        # Test metrics
        tests_total = test_metrics.get("tests_total", 0)
        tests_passed = test_metrics.get("tests_passed", 0)
        tests_failed = test_metrics.get("tests_failures", 0)
        tests_skipped = test_metrics.get("tests_skipped", 0)
        success_rate = test_metrics.get("success_rate", 0.0)
        
        # Coverage metrics
        line_coverage = coverage_metrics.get("line_coverage_percent", 0.0)
        branch_coverage = coverage_metrics.get("branch_coverage_percent", 0.0)
        
        # Store run information
        await conn.execute(
            """
            INSERT INTO runs (
                id, repo_path, timestamp, overall_success,
                tests_total, tests_passed, tests_failed, tests_skipped,
                success_rate, line_coverage_percent, branch_coverage_percent,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, str(repo_path), timestamp, 1 if overall_success else 0,
                tests_total, tests_passed, tests_failed, tests_skipped,
                success_rate, line_coverage, branch_coverage,
                json.dumps(metadata) if metadata else None
            )
        )
        
        # Store package data
        packages = coverage_metrics.get("packages", [])
        for package in packages:
            package_id = str(uuid.uuid4())
            package_name = package.get("name", "")
            package_coverage = package.get("line_coverage_percent", 0.0)
            
            await conn.execute(
                """
                INSERT INTO packages (id, run_id, package_name, line_coverage_percent)
                VALUES (?, ?, ?, ?)
                """,
                (package_id, run_id, package_name, package_coverage)
            )
            
            # Store file data
            files = package.get("files", [])
            for file_data in files:
                file_id = str(uuid.uuid4())
                file_name = file_data.get("name", "")
                file_coverage = file_data.get("line_coverage_percent", 0.0)
                
                await conn.execute(
                    """
                    INSERT INTO files (id, run_id, package_name, file_name, line_coverage_percent)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (file_id, run_id, package_name, file_name, file_coverage)
                )
        
        await conn.commit()
        logger.info(f"Stored snapshot with run ID {run_id}")
        return run_id
    except Exception as e:
        await conn.rollback()
        raise SnapshotDBError(f"Failed to store snapshot: {str(e)}")
    finally:
        await conn.close()


async def get_run(db_path: Union[str, Path], run_id: str) -> Dict[str, Any]:
    """Get a specific run by ID.

    Args:
        db_path: Path to the SQLite database file
        run_id: The ID of the run to retrieve

    Returns:
        Dictionary with run data

    Raises:
        SnapshotDBError: If there's an error retrieving the run
    """
    try:
        conn = await aiosqlite.connect(str(db_path))
        conn.row_factory = aiosqlite.Row
        
        # Get the run by ID
        cursor = await conn.execute(
            """
            SELECT * FROM runs WHERE id = ?
            """,
            (run_id,)
        )
        run = await cursor.fetchone()
        if not run:
            await conn.close()
            return None
            
        # Convert to dict
        run_dict = dict(run)
        
        # Get file data
        cursor = await conn.execute(
            """
            SELECT * FROM files WHERE run_id = ?
            """,
            (run_id,)
        )
        files = await cursor.fetchall()
        run_dict["files"] = [dict(file) for file in files]
        
        # Get package data
        cursor = await conn.execute(
            """
            SELECT * FROM packages WHERE run_id = ?
            """,
            (run_id,)
        )
        packages = await cursor.fetchall()
        run_dict["packages"] = [dict(package) for package in packages]
        
        await conn.close()
        return run_dict
    except Exception as e:
        if 'conn' in locals() and conn:
            await conn.close()
        raise SnapshotDBError(f"Failed to retrieve run: {str(e)}")


async def list_runs(
    db_path: Union[str, Path], 
    limit: int = 10, 
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List runs with pagination.

    Args:
        db_path: Path to the SQLite database file
        limit: Maximum number of runs to return
        offset: Offset for pagination

    Returns:
        List of run dictionaries, ordered by timestamp (newest first)

    Raises:
        SnapshotDBError: If there's an error listing runs
    """
    try:
        conn = await aiosqlite.connect(str(db_path))
        conn.row_factory = aiosqlite.Row
        
        query = """
            SELECT id, repo_path, timestamp, overall_success, 
                   tests_total, tests_passed, success_rate, line_coverage_percent
            FROM runs
            ORDER BY timestamp DESC
        """
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            cursor = await conn.execute(query, (limit, offset))
        else:
            cursor = await conn.execute(query)
        
        runs = [dict(row) for row in await cursor.fetchall()]
        
        # Convert SQLite integers to booleans
        for run in runs:
            run["overall_success"] = bool(run["overall_success"])
        
        await conn.close()
        return runs
    except Exception as e:
        if 'conn' in locals() and conn:
            await conn.close()
        raise SnapshotDBError(f"Failed to list runs: {str(e)}")


async def get_runs_count(db_path: Union[str, Path]) -> int:
    """Get the total count of runs in the database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Total number of runs

    Raises:
        SnapshotDBError: If there's an error counting runs
    """
    try:
        conn = await aiosqlite.connect(str(db_path))
        
        query = """
            SELECT COUNT(*) as count FROM runs
        """
        
        cursor = await conn.execute(query)
        row = await cursor.fetchone()
        count = row[0] if row else 0
        
        await conn.close()
        return count
    except Exception as e:
        if 'conn' in locals() and conn:
            await conn.close()
        raise SnapshotDBError(f"Failed to count runs: {str(e)}") 