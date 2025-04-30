from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from engine.commit import CommitResult, format_python_file, get_commit_message, apply_and_commit
from engine.patch import PatchResponse
from models.plan_item import PlanItem

@pytest.fixture
def plan_item():
    return PlanItem(
        id="test-123",
        file_path="crawler/test.py",
        action="MODIFY",
        reason="Add error handling",
        confidence=0.9,
    )

@pytest.fixture
def patch_response():
    return PatchResponse(
        diff="""--- a/crawler/test.py
+++ b/crawler/test.py
@@ -1,2 +1,5 @@
+try:
     result = process()
+except Exception as e:
+    logger.error("Failed", extra={"error": str(e)})
""",
        confidence=0.95,
    )

@pytest.mark.asyncio
async def test_format_python_file_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = await format_python_file(Path("test.py"))
        assert result is True
        assert mock_run.call_count == 2  # black and ruff

@pytest.mark.asyncio
async def test_format_python_file_black_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Black error"
        )
        result = await format_python_file(Path("test.py"))
        assert result is False
        assert mock_run.call_count == 1  # only black

@pytest.mark.asyncio
async def test_format_python_file_ruff_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),  # black succeeds
            MagicMock(returncode=1, stderr="Ruff error"),  # ruff fails
        ]
        result = await format_python_file(Path("test.py"))
        assert result is False
        assert mock_run.call_count == 2

def test_get_commit_message():
    # Test ADD action
    item = PlanItem(
        id="test-123",
        file_path="crawler/test.py",
        action="ADD",
        reason="Add new feature",
        confidence=0.9,
    )
    msg = get_commit_message(item)
    assert msg.startswith("feat(crawler):")
    assert "Add new feature" in msg
    assert "Plan-Item: test-123" in msg

    # Test MODIFY action
    item.action = "MODIFY"
    msg = get_commit_message(item)
    assert msg.startswith("fix(crawler):")

    # Test DELETE action
    item.action = "DELETE"
    msg = get_commit_message(item)
    assert msg.startswith("refactor(crawler):")

    # Test unknown action
    item.action = "UNKNOWN"  # type: ignore
    msg = get_commit_message(item)
    assert msg.startswith("chore(crawler):")

@pytest.mark.asyncio
async def test_apply_and_commit_success(plan_item, patch_response):
    mock_results = [
        MagicMock(returncode=0),  # git apply
        MagicMock(returncode=0),  # black
        MagicMock(returncode=0),  # ruff
        MagicMock(returncode=0),  # git add
        MagicMock(returncode=0),  # git commit
        MagicMock(returncode=0, stdout="abc123\n"),  # git rev-parse
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = mock_results
        
        result = await apply_and_commit(
            patch_response,
            plan_item,
            Path("/test/repo"),
        )
        
        assert result.success is True
        assert result.commit_hash == "abc123"
        assert mock_run.call_count == 6

@pytest.mark.asyncio
async def test_apply_and_commit_patch_failure(plan_item, patch_response):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=b"Failed to apply patch"
        )
        
        result = await apply_and_commit(
            patch_response,
            plan_item,
            Path("/test/repo"),
        )
        
        assert result.success is False
        assert "Failed to apply patch" in result.error_message
        assert mock_run.call_count == 1

@pytest.mark.asyncio
async def test_apply_and_commit_format_failure(plan_item, patch_response):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git apply succeeds
            MagicMock(returncode=1, stderr="Black error"),  # black fails
        ]
        
        result = await apply_and_commit(
            patch_response,
            plan_item,
            Path("/test/repo"),
        )
        
        assert result.success is False
        assert "Failed to format" in result.error_message
        assert mock_run.call_count == 2

@pytest.mark.asyncio
async def test_apply_and_commit_commit_failure(plan_item, patch_response):
    mock_results = [
        MagicMock(returncode=0),  # git apply
        MagicMock(returncode=0),  # black
        MagicMock(returncode=0),  # ruff
        MagicMock(returncode=0),  # git add
        MagicMock(returncode=1, stderr="Commit failed"),  # git commit
    ]
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = mock_results
        
        result = await apply_and_commit(
            patch_response,
            plan_item,
            Path("/test/repo"),
        )
        
        assert result.success is False
        assert "Failed to create commit" in result.error_message
        assert mock_run.call_count == 5 