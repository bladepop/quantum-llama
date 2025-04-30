from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from engine.patch import PatchResponse
from models.plan_item import PlanItem

logger = logging.getLogger(__name__)

class CommitResult(BaseModel):
    """Result of a commit operation."""
    success: bool
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None

async def format_python_file(file_path: Path) -> bool:
    """Format a Python file using black and ruff.
    
    Args:
        file_path: Path to the Python file to format.
        
    Returns:
        True if formatting was successful, False otherwise.
    """
    try:
        # Run black
        black_result = subprocess.run(
            ["black", str(file_path)],
            capture_output=True,
            text=True,
        )
        if black_result.returncode != 0:
            logger.error(
                "Black formatting failed",
                extra={
                    "file": str(file_path),
                    "error": black_result.stderr,
                }
            )
            return False

        # Run ruff --fix
        ruff_result = subprocess.run(
            ["ruff", "--fix", str(file_path)],
            capture_output=True,
            text=True,
        )
        if ruff_result.returncode != 0:
            logger.error(
                "Ruff fix failed",
                extra={
                    "file": str(file_path),
                    "error": ruff_result.stderr,
                }
            )
            return False

        return True

    except Exception as e:
        logger.exception("Error formatting Python file")
        return False

def get_commit_message(plan_item: PlanItem) -> str:
    """Generate a conventional commit message for a plan item.
    
    Args:
        plan_item: The plan item to generate a commit message for.
        
    Returns:
        A conventional commit message string.
    """
    # Map plan item action to commit type
    action_to_type = {
        "ADD": "feat",
        "MODIFY": "fix",
        "DELETE": "refactor",
        "RENAME": "refactor",
    }
    commit_type = action_to_type.get(plan_item.action, "chore")
    
    # Extract scope from file path (e.g., crawler/clone.py -> crawler)
    scope = Path(plan_item.file_path).parts[0] if "/" in plan_item.file_path else None
    scope_str = f"({scope})" if scope else ""
    
    # Construct commit message
    message = f"{commit_type}{scope_str}: {plan_item.reason}"
    
    # Add plan item ID as trailer
    message += f"\n\nPlan-Item: {plan_item.id}"
    
    return message

async def apply_and_commit(
    patch_response: PatchResponse,
    plan_item: PlanItem,
    repo_root: Path,
) -> CommitResult:
    """Apply a patch, format the code, and create a commit.
    
    Args:
        patch_response: The patch to apply.
        plan_item: The plan item being implemented.
        repo_root: The root directory of the repository.
        
    Returns:
        A CommitResult indicating success or failure.
    """
    try:
        # Apply the patch
        apply_result = subprocess.run(
            ["git", "apply"],
            input=patch_response.diff.encode(),
            cwd=repo_root,
            capture_output=True,
        )
        
        if apply_result.returncode != 0:
            return CommitResult(
                success=False,
                error_message=f"Failed to apply patch: {apply_result.stderr.decode()}"
            )

        # Format Python files if applicable
        if plan_item.file_path.endswith(".py"):
            format_success = await format_python_file(repo_root / plan_item.file_path)
            if not format_success:
                return CommitResult(
                    success=False,
                    error_message="Failed to format Python file"
                )

        # Stage the changes
        stage_result = subprocess.run(
            ["git", "add", plan_item.file_path],
            cwd=repo_root,
            capture_output=True,
        )
        
        if stage_result.returncode != 0:
            return CommitResult(
                success=False,
                error_message=f"Failed to stage changes: {stage_result.stderr.decode()}"
            )

        # Create the commit
        commit_message = get_commit_message(plan_item)
        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        
        if commit_result.returncode != 0:
            return CommitResult(
                success=False,
                error_message=f"Failed to create commit: {commit_result.stderr}"
            )

        # Extract commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None

        logger.info(
            "Successfully applied patch and created commit",
            extra={
                "file": plan_item.file_path,
                "commit_hash": commit_hash,
                "plan_item_id": plan_item.id,
            }
        )

        return CommitResult(
            success=True,
            commit_hash=commit_hash,
        )

    except Exception as e:
        logger.exception("Error in apply_and_commit")
        return CommitResult(
            success=False,
            error_message=str(e)
        ) 