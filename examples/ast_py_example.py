#!/usr/bin/env python
"""Example of using the Python AST builder."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from crawler.ast_py import parse_python_file, parse_directory, save_ast_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the AST parser example.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Check command-line arguments
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_or_directory_path> [output_file]")
        return 1

    # Get the path argument
    path = Path(sys.argv[1])
    
    # Get the output path if provided, or use a default
    output_path = None
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    
    # Parse the file or directory
    if path.is_file():
        logger.info(f"Parsing file: {path}")
        ast = parse_python_file(path)
        
        # Default output for a file
        if output_path is None:
            output_path = path.with_suffix(".ast.json")
    elif path.is_dir():
        logger.info(f"Parsing directory: {path}")
        ast = parse_directory(path)
        
        # Default output for a directory
        if output_path is None:
            output_path = path / "ast_output.json"
    else:
        logger.error(f"Path does not exist or is not a file or directory: {path}")
        return 1
    
    # Check if we got an error
    if "error" in ast:
        logger.error(f"Error parsing {path}: {ast['error']}")
        return 1
    
    # Save the AST to a JSON file
    save_ast_to_json(ast, output_path)
    logger.info(f"AST saved to {output_path}")
    
    # Print a sample of the AST if it's not too large
    ast_str = json.dumps(ast, indent=2)
    if len(ast_str) > 1000:
        logger.info(f"AST excerpt (first 1000 chars):\n{ast_str[:1000]}...")
    else:
        logger.info(f"AST:\n{ast_str}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 