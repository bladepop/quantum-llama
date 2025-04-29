#!/usr/bin/env python
"""Example of using the concurrent repository cloner."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from models.target_repo import TargetRepo
from crawler.clone import clone_repos

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main() -> None:
    """Run the repository cloning example."""
    # Define repositories to clone
    repos = [
        TargetRepo(
            url="https://github.com/psf/black",
            language="python",
        ),
        TargetRepo(
            url="https://github.com/astral-sh/ruff",
            language="python",
        ),
    ]

    # Set destination directory
    dest_dir = Path("./cloned_repos")

    try:
        # Clone repositories concurrently
        cloned_paths = await clone_repos(repos, dest_dir)
        
        # Print results
        print(f"Successfully cloned {len(cloned_paths)} repositories:")
        for path in cloned_paths:
            print(f"  - {path}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 