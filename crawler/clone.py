"""Repository cloning utilities with concurrency and retry support."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List

import anyio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from models.target_repo import TargetRepo

logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Exception raised when a git clone operation fails."""

    def __init__(self, repo_url: str, error_msg: str):
        """Initialize with repo URL and error message.

        Args:
            repo_url: The repository URL that failed to clone
            error_msg: The error message from the git command
        """
        self.repo_url = repo_url
        self.error_msg = error_msg
        super().__init__(f"Failed to clone {repo_url}: {error_msg}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(CloneError),
    reraise=True,
)
async def _clone_single_repo(repo: TargetRepo, dest_dir: Path) -> Path:
    """Clone a single repository with retries.

    Args:
        repo: Repository to clone
        dest_dir: Base directory where repositories will be cloned

    Returns:
        Path to the cloned repository directory

    Raises:
        CloneError: If the clone operation fails after retries
    """
    # Create a directory name from the repo URL
    repo_url = str(repo.url)
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_dir = dest_dir / repo_name

    # Clean up existing directory if it exists
    if repo_dir.exists():
        logger.info(f"Removing existing directory {repo_dir}")
        shutil.rmtree(repo_dir)

    logger.info(f"Cloning {repo_url} to {repo_dir}")

    try:
        # Use subprocess to run git clone
        process = await anyio.run_process(
            [
                "git",
                "clone",
                "--branch",
                repo.default_branch,
                "--single-branch",
                repo_url,
                str(repo_dir),
            ],
            capture_stdout=True,
            capture_stderr=True,
        )
        logger.debug(f"Clone successful: {process.stdout.decode()}")
        return repo_dir
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if hasattr(e, "stderr") else str(e)
        logger.error(f"Clone failed: {error_msg}")
        raise CloneError(repo_url, error_msg)


async def clone_repos(repos: List[TargetRepo], dest_dir: Path) -> List[Path]:
    """Clone multiple repositories concurrently with retry logic.

    Args:
        repos: List of repositories to clone
        dest_dir: Base directory where repositories will be cloned

    Returns:
        List of paths to the cloned repository directories
    """
    # Ensure the destination directory exists
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Cloning {len(repos)} repositories to {dest_dir}")

    # Use anyio TaskGroup for concurrent cloning
    async with anyio.create_task_group() as tg:
        clone_tasks = []

        for repo in repos:
            task = tg.start_soon(
                _clone_single_repo, repo, dest_dir, name=f"clone-{repo.url}"
            )
            clone_tasks.append(task)

    # Collect results
    result_paths = []
    for repo in repos:
        repo_url = str(repo.url)
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_dir = dest_dir / repo_name
        if repo_dir.exists():
            result_paths.append(repo_dir)

    return result_paths 