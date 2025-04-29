#!/usr/bin/env python3
"""Command-line utility for querying snapshot data from the SQLite database."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from tabulate import tabulate

from crawler import snapshot_db

logger = logging.getLogger(__name__)


async def list_recent_runs(db_path: Union[str, Path], limit: int) -> None:
    """List recent runs from the database.

    Args:
        db_path: Path to the SQLite database file
        limit: Maximum number of runs to list
    """
    try:
        runs = await snapshot_db.list_runs(db_path, limit=limit)
        total_runs = await snapshot_db.get_runs_count(db_path)

        if not runs:
            print("No runs found in the database.")
            return

        # Prepare data for table format
        headers = [
            "Run ID", "Timestamp", "Repository", "Tests Passed", 
            "Test Success", "Coverage"
        ]
        
        rows = []
        for run in runs:
            rows.append([
                run["id"][:8] + "...",  # Truncate ID for display
                run["timestamp"].split("T")[0],  # Just the date part
                Path(run["repo_path"]).name,  # Just the repo name
                f"{run['tests_passed']}/{run['tests_total']}",
                f"{run['success_rate']:.1f}%",
                f"{run['line_coverage_percent']:.1f}%"
            ])
        
        print(f"\nRecent Runs ({len(runs)} of {total_runs} total):")
        print(tabulate(rows, headers=headers, tablefmt="grid"))
        print(f"\nTo view details for a specific run, use: query_snapshots.py show <run_id>")
    
    except snapshot_db.SnapshotDBError as e:
        logger.error(f"Error listing runs: {e}")
        sys.exit(1)


async def show_run_details(db_path: Union[str, Path], run_id: str) -> None:
    """Show detailed information about a specific run.

    Args:
        db_path: Path to the SQLite database file
        run_id: ID of the run to show
    """
    try:
        run = await snapshot_db.get_run(db_path, run_id)
        
        # Print run overview
        print(f"\nRun ID: {run['id']}")
        print(f"Repository: {run['repo_path']}")
        print(f"Timestamp: {run['timestamp']}")
        print(f"Status: {'Success' if run['overall_success'] else 'Failure'}")
        print("\nTest Results:")
        print(f"  Total Tests: {run['tests_total']}")
        print(f"  Passed: {run['tests_passed']}")
        print(f"  Failed: {run['tests_failed']}")
        print(f"  Skipped: {run['tests_skipped']}")
        print(f"  Success Rate: {run['success_rate']:.1f}%")
        
        print("\nCoverage Results:")
        print(f"  Line Coverage: {run['line_coverage_percent']:.1f}%")
        print(f"  Branch Coverage: {run['branch_coverage_percent']:.1f}%")
        
        # Print metadata if available
        if run.get("metadata"):
            print("\nMetadata:")
            for key, value in run["metadata"].items():
                print(f"  {key}: {value}")
        
        # Print package summaries
        if run.get("packages"):
            print("\nPackage Coverage:")
            
            # Prepare data for table format
            headers = ["Package", "Coverage", "Files"]
            rows = []
            
            for pkg_name, pkg_data in run["packages"].items():
                rows.append([
                    pkg_name,
                    f"{pkg_data['line_coverage_percent']:.1f}%",
                    len(pkg_data['files'])
                ])
            
            print(tabulate(rows, headers=headers, tablefmt="grid"))
            
            # Offer to show file details
            print("\nTo view file-level details, use: query_snapshots.py files <run_id> <package_name>")
    
    except snapshot_db.SnapshotDBError as e:
        logger.error(f"Error retrieving run: {e}")
        sys.exit(1)


async def show_file_details(db_path: Union[str, Path], run_id: str, package_name: str) -> None:
    """Show file-level details for a specific package in a run.

    Args:
        db_path: Path to the SQLite database file
        run_id: ID of the run to show
        package_name: Name of the package to show files for
    """
    try:
        run = await snapshot_db.get_run(db_path, run_id)
        
        if not run.get("packages") or package_name not in run["packages"]:
            print(f"Package '{package_name}' not found in run {run_id}")
            return
        
        package_data = run["packages"][package_name]
        
        print(f"\nFiles in package '{package_name}' (Run ID: {run_id[:8]}...):")
        print(f"Package Coverage: {package_data['line_coverage_percent']:.1f}%")
        
        # Prepare data for table format
        headers = ["File", "Coverage"]
        rows = []
        
        for file_data in package_data["files"]:
            rows.append([
                file_data["file_name"],
                f"{file_data['line_coverage_percent']:.1f}%"
            ])
        
        # Sort by coverage (ascending)
        rows.sort(key=lambda x: float(x[1].rstrip('%')))
        
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    
    except snapshot_db.SnapshotDBError as e:
        logger.error(f"Error retrieving file details: {e}")
        sys.exit(1)


async def compare_runs(db_path: Union[str, Path], run_id1: str, run_id2: str) -> None:
    """Compare two runs to show changes in metrics.

    Args:
        db_path: Path to the SQLite database file
        run_id1: ID of the first run (baseline)
        run_id2: ID of the second run (comparison)
    """
    try:
        run1 = await snapshot_db.get_run(db_path, run_id1)
        run2 = await snapshot_db.get_run(db_path, run_id2)
        
        # Print basic comparison info
        print(f"\nComparing Runs:")
        print(f"  Baseline: {run1['id'][:8]}... ({run1['timestamp'].split('T')[0]})")
        print(f"  Current:  {run2['id'][:8]}... ({run2['timestamp'].split('T')[0]})")
        
        # Calculate metric changes
        test_delta = run2["tests_passed"] - run1["tests_passed"]
        test_rate_delta = run2["success_rate"] - run1["success_rate"]
        coverage_delta = run2["line_coverage_percent"] - run1["line_coverage_percent"]
        
        # Print metric comparisons
        print("\nMetric Changes:")
        print(f"  Tests Passed: {run1['tests_passed']} → {run2['tests_passed']} " 
              f"({'↑' if test_delta > 0 else '↓' if test_delta < 0 else '='}{abs(test_delta)})")
        
        print(f"  Success Rate: {run1['success_rate']:.1f}% → {run2['success_rate']:.1f}% "
              f"({'↑' if test_rate_delta > 0 else '↓' if test_rate_delta < 0 else '='}{abs(test_rate_delta):.1f}%)")
        
        print(f"  Line Coverage: {run1['line_coverage_percent']:.1f}% → {run2['line_coverage_percent']:.1f}% "
              f"({'↑' if coverage_delta > 0 else '↓' if coverage_delta < 0 else '='}{abs(coverage_delta):.1f}%)")
        
        # Compare packages if they exist in both runs
        if run1.get("packages") and run2.get("packages"):
            print("\nPackage Coverage Changes:")
            
            # Get common packages
            common_packages = set(run1["packages"].keys()) & set(run2["packages"].keys())
            
            if common_packages:
                # Prepare data for table format
                headers = ["Package", "Before", "After", "Change"]
                rows = []
                
                for pkg_name in common_packages:
                    pkg1_cov = run1["packages"][pkg_name]["line_coverage_percent"]
                    pkg2_cov = run2["packages"][pkg_name]["line_coverage_percent"]
                    pkg_delta = pkg2_cov - pkg1_cov
                    
                    rows.append([
                        pkg_name,
                        f"{pkg1_cov:.1f}%",
                        f"{pkg2_cov:.1f}%",
                        f"{'↑' if pkg_delta > 0 else '↓' if pkg_delta < 0 else '='}{abs(pkg_delta):.1f}%"
                    ])
                
                # Sort by absolute change (descending)
                rows.sort(key=lambda x: abs(float(x[3][1:-1])), reverse=True)
                
                print(tabulate(rows, headers=headers, tablefmt="grid"))
    
    except snapshot_db.SnapshotDBError as e:
        logger.error(f"Error comparing runs: {e}")
        sys.exit(1)


async def export_run_data(db_path: Union[str, Path], run_id: str, output_path: str) -> None:
    """Export run data to a JSON file.

    Args:
        db_path: Path to the SQLite database file
        run_id: ID of the run to export
        output_path: Path to the output JSON file
    """
    try:
        run = await snapshot_db.get_run(db_path, run_id)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(run, f, indent=2)
        
        print(f"Run data exported to {output_path}")
    
    except snapshot_db.SnapshotDBError as e:
        logger.error(f"Error exporting run data: {e}")
        sys.exit(1)


def main() -> int:
    """Run the snapshot query tool from the command line.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Query and display snapshot data from the SQLite database"
    )
    parser.add_argument(
        "-d", "--db", default="data/crawl.db",
        help="Path to the SQLite database file (default: data/crawl.db)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose output"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List subcommand
    list_parser = subparsers.add_parser("list", help="List recent runs")
    list_parser.add_argument(
        "-n", "--limit", type=int, default=10,
        help="Maximum number of runs to list (default: 10)"
    )
    
    # Show subcommand
    show_parser = subparsers.add_parser("show", help="Show details for a specific run")
    show_parser.add_argument("run_id", help="ID of the run to show")
    
    # Files subcommand
    files_parser = subparsers.add_parser("files", help="Show file details for a package")
    files_parser.add_argument("run_id", help="ID of the run to show")
    files_parser.add_argument("package", help="Name of the package to show files for")
    
    # Compare subcommand
    compare_parser = subparsers.add_parser("compare", help="Compare two runs")
    compare_parser.add_argument("run_id1", help="ID of the first run (baseline)")
    compare_parser.add_argument("run_id2", help="ID of the second run (comparison)")
    
    # Export subcommand
    export_parser = subparsers.add_parser("export", help="Export run data to a JSON file")
    export_parser.add_argument("run_id", help="ID of the run to export")
    export_parser.add_argument("output", help="Path to the output JSON file")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Check if the database file exists
    if not Path(args.db).exists():
        logger.error(f"Database file does not exist: {args.db}")
        return 1
    
    # Process commands
    if args.command == "list":
        asyncio.run(list_recent_runs(args.db, args.limit))
    elif args.command == "show":
        asyncio.run(show_run_details(args.db, args.run_id))
    elif args.command == "files":
        asyncio.run(show_file_details(args.db, args.run_id, args.package))
    elif args.command == "compare":
        asyncio.run(compare_runs(args.db, args.run_id1, args.run_id2))
    elif args.command == "export":
        asyncio.run(export_run_data(args.db, args.run_id, args.output))
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 