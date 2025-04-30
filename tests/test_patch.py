from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from engine.patch import PatchRequest, PatchResponse, generate_patch, apply_patch
from models.plan_item import PlanItem

@pytest.fixture
def plan_item():
    return PlanItem(
        id="test-id",
        file_path="test.py",
        action="MODIFY",
        reason="Add logging",
        confidence=0.9,
    )

@pytest.fixture
def file_content():
    return """def hello():
    print("Hello")
"""

@pytest.fixture
def mock_openai_response():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""--- a/test.py
+++ b/test.py
@@ -1,2 +1,5 @@
+import logging
+
+logger = logging.getLogger(__name__)
 def hello():
-    print("Hello")
+    logger.info("Hello")
"""
            ),
            finish_reason="stop",
        )
    ]
    return mock_response

@pytest.mark.asyncio
async def test_generate_patch(plan_item, file_content, mock_openai_response):
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_openai_response

    request = PatchRequest(
        plan_item=plan_item,
        file_content=file_content,
        base_commit="abc123",
    )

    response = await generate_patch(request, mock_client)
    assert isinstance(response, PatchResponse)
    assert "logger.info" in response.diff
    assert response.confidence == 1.0

@pytest.mark.asyncio
async def test_generate_patch_empty_content(plan_item):
    mock_client = AsyncMock()
    
    request = PatchRequest(
        plan_item=plan_item,
        file_content="",
        base_commit="abc123",
    )

    with pytest.raises(ValueError, match="File content cannot be empty"):
        await generate_patch(request, mock_client)

@pytest.mark.asyncio
async def test_apply_patch_success():
    patch = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,3 @@
+import logging
 def hello():
     print("Hello")
"""
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = await apply_patch(patch, Path("/test/repo"))
        assert result is True
        mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_apply_patch_failure():
    patch = "invalid patch"
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = b"Failed to apply patch"
        result = await apply_patch(patch, Path("/test/repo"))
        assert result is False
        mock_run.assert_called_once() 