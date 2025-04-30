from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from crawler.baseline import parse_coverage_xml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def load_baseline_coverage(baseline_file: Path) -> Dict[str, Any]:
    """Load baseline coverage metrics from a JSON file.
    
    Args:
        baseline_file: Path to the baseline coverage JSON file
        
    Returns:
        Dictionary containing baseline coverage metrics
        
    Raises:
        FileNotFoundError: If baseline file doesn't exist
        json.JSONDecodeError: If baseline file is invalid JSON
    """
    with open(baseline_file, "r", encoding="utf-8") as f:
        return json.load(f)

def check_coverage_diff(
    current_coverage: Dict[str, Any],
    baseline_coverage: Dict[str, Any],
    min_coverage: float = 90.0,
    max_decrease: float = 0.5,
) -> tuple[bool, str]:
    """Check if coverage changes are within acceptable limits.
    
    Args:
        current_coverage: Current coverage metrics
        baseline_coverage: Baseline coverage metrics
        min_coverage: Minimum required coverage percentage
        max_decrease: Maximum allowed coverage decrease percentage
        
    Returns:
        Tuple of (passed: bool, message: str)
    """
    current = current_coverage["line_coverage_percent"]
    baseline = baseline_coverage["line_coverage_percent"]
    diff = current - baseline
    
    # Build status message
    msg_parts = [
        f"Coverage: {current:.1f}% (baseline: {baseline:.1f}%, diff: {diff:+.1f}%)",
    ]
    
    # Check minimum coverage requirement
    if current < min_coverage:
        msg_parts.append(
            f"❌ Coverage below minimum required ({min_coverage:.1f}%)"
        )
        return False, "\n".join(msg_parts)
    
    # Check maximum decrease
    if diff < -max_decrease:
        msg_parts.append(
            f"❌ Coverage decrease ({abs(diff):.1f}%) exceeds maximum allowed ({max_decrease:.1f}%)"
        )
        return False, "\n".join(msg_parts)
    
    # Add package-level changes if available
    if "packages" in current_coverage and "packages" in baseline_coverage:
        current_pkgs = {
            pkg["name"]: pkg["line_coverage_percent"]
            for pkg in current_coverage["packages"]
        }
        baseline_pkgs = {
            pkg["name"]: pkg["line_coverage_percent"]
            for pkg in baseline_coverage["packages"]
        }
        
        # Find packages with significant changes
        sig_changes = []
        for pkg in set(current_pkgs) & set(baseline_pkgs):
            pkg_diff = current_pkgs[pkg] - baseline_pkgs[pkg]
            if abs(pkg_diff) >= 0.5:  # Only show significant changes
                sig_changes.append(
                    f"  {pkg}: {current_pkgs[pkg]:.1f}% ({pkg_diff:+.1f}%)"
                )
        
        if sig_changes:
            msg_parts.append("\nSignificant package changes:")
            msg_parts.extend(sig_changes)
    
    msg_parts.append("✅ Coverage checks passed")
    return True, "\n".join(msg_parts)

def main() -> int:
    """Main entry point for coverage diff checker."""
    parser = argparse.ArgumentParser(description="Check coverage diff against baseline")
    parser.add_argument(
        "--coverage-xml",
        type=Path,
        required=True,
        help="Path to current coverage.xml file"
    )
    parser.add_argument(
        "--baseline-json",
        type=Path,
        required=True,
        help="Path to baseline coverage JSON file"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=90.0,
        help="Minimum required coverage percentage"
    )
    parser.add_argument(
        "--max-decrease",
        type=float,
        default=0.5,
        help="Maximum allowed coverage decrease percentage"
    )
    
    args = parser.parse_args()
    
    try:
        # Parse current coverage
        current_coverage = parse_coverage_xml(args.coverage_xml)
        
        # Load baseline coverage
        baseline_coverage = load_baseline_coverage(args.baseline_json)
        
        # Check coverage diff
        passed, message = check_coverage_diff(
            current_coverage,
            baseline_coverage,
            args.min_coverage,
            args.max_decrease
        )
        
        # Print results
        print("\nCoverage Diff Check Results")
        print("=" * 30)
        print(message)
        
        return 0 if passed else 1
        
    except Exception as e:
        logger.error(f"Error checking coverage diff: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 