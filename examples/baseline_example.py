#!/usr/bin/env python
"""Example of using the baseline metrics collector."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from crawler.baseline import collect_baseline_metrics, save_metrics_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the baseline metrics collector on the current project.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Collect baseline metrics for this project")
    parser.add_argument("-o", "--output", default="baseline_metrics.json", 
                        help="Path to the output JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Set log level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get the current project directory (repo root)
    current_dir = Path(__file__).parent.parent
    
    try:
        logger.info(f"Collecting baseline metrics for {current_dir}")
        
        # Add specific pytest arguments for our project
        pytest_args = [
            "--cov=crawler",
            "--cov=models",
            "--cov=tests",
        ]
        
        # Collect metrics
        metrics = collect_baseline_metrics(current_dir, pytest_args)
        
        # Save to JSON
        output_path = Path(args.output)
        save_metrics_to_json(metrics, output_path)
        
        # Print summary of results
        print("\n=== Baseline Metrics Summary ===")
        print(f"Overall success: {'✅' if metrics['overall_success'] else '❌'}")
        
        tests = metrics["tests"]
        print(f"\nTests: {tests['tests_passed']}/{tests['tests_total']} passed "
              f"({tests['success_rate']:.1f}%)")
        if tests["tests_failures"] > 0:
            print(f"Failed tests: {tests['tests_failures']}")
        if tests["tests_skipped"] > 0:
            print(f"Skipped tests: {tests['tests_skipped']}")
        
        coverage = metrics["coverage"]
        print(f"\nLine coverage: {coverage['line_coverage_percent']:.1f}%")
        if "branch_coverage_percent" in coverage:
            print(f"Branch coverage: {coverage['branch_coverage_percent']:.1f}%")
        
        print(f"\nDetailed metrics saved to: {output_path.absolute()}")
        return 0
    except Exception as e:
        logger.error(f"Error collecting metrics: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 