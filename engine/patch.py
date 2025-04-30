from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from openai import AsyncClient
from pydantic import BaseModel

from models.plan_item import PlanItem

logger = logging.getLogger(__name__)

class PatchRequest(BaseModel):
    """Request model for generating a patch."""
    plan_item: PlanItem
    file_content: str
    base_commit: str

class PatchResponse(BaseModel):
    """Response model containing the generated patch."""
    diff: str
    confidence: float

async def generate_patch(
    request: PatchRequest,
    openai_client: AsyncClient,
    model: str = "gpt-4-turbo-preview",
) -> PatchResponse:
    """Generate a unified diff patch using LLM for the given plan item.
    
    Args:
        request: The patch request containing plan item and file content.
        openai_client: The OpenAI client instance.
        model: The OpenAI model to use for generation.
        
    Returns:
        A PatchResponse containing the generated diff and confidence score.
        
    Raises:
        ValueError: If the file content is empty or the plan item is invalid.
    """
    if not request.file_content:
        raise ValueError("File content cannot be empty")

    # Construct the prompt for patch generation
    prompt = f"""Generate a unified diff that implements the following change:

File: {request.plan_item.file_path}
Reason: {request.plan_item.reason}

Current file content:
```
{request.file_content}
```

Requirements:
1. Output ONLY the unified diff format (no explanations)
2. Include minimal context lines around changes
3. Follow Python best practices (if Python file)
4. Ensure the patch can be applied cleanly
5. Do not include file mode changes

Example format:
```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,7 +10,7 @@
 unchanged line
-removed line
+added line
 unchanged line
```
"""

    # Call OpenAI API to generate the patch
    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a code modification expert that generates precise unified diffs."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,  # Low temperature for more deterministic output
        max_tokens=2000,
    )

    # Extract the diff from the response
    diff = response.choices[0].message.content.strip()
    
    # Calculate confidence based on response
    confidence = response.choices[0].finish_reason == "stop"
    
    # Log the generation attempt
    logger.info(
        "Generated patch",
        extra={
            "file_path": request.plan_item.file_path,
            "confidence": confidence,
            "base_commit": request.base_commit,
        }
    )

    return PatchResponse(
        diff=diff,
        confidence=float(confidence),
    )

async def apply_patch(
    patch: str,
    repo_root: Path,
    dry_run: bool = False,
) -> bool:
    """Apply a unified diff patch to the repository.
    
    Args:
        patch: The unified diff patch to apply.
        repo_root: The root directory of the repository.
        dry_run: If True, only test if the patch can be applied.
        
    Returns:
        True if the patch was applied successfully, False otherwise.
    """
    import subprocess
    
    try:
        cmd = ["git", "apply", "--check" if dry_run else ""]
        proc = subprocess.run(
            cmd,
            input=patch.encode(),
            cwd=repo_root,
            capture_output=True,
        )
        success = proc.returncode == 0
        
        if not success:
            logger.error(
                "Failed to apply patch",
                extra={
                    "error": proc.stderr.decode(),
                    "dry_run": dry_run,
                }
            )
        
        return success
        
    except Exception as e:
        logger.exception("Error applying patch")
        return False 