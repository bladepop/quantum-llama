"""Tests for the repository cloning utilities."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import anyio
import pytest
from tenacity import stop_after_attempt

from crawler.clone import clone_repos, _clone_single_repo, CloneError
from models.target_repo import TargetRepo


@pytest.fixture
def mock_process():
    """Create a mock process result."""
    mock = MagicMock()
    mock.stdout = b"Cloning into 'repo'...\nDone."
    return mock


@pytest.fixture
def test_repos():
    """Create test repository objects."""
    return [
        TargetRepo(
            url="https://github.com/example/repo1",
            language="python",
        ),
        TargetRepo(
            url="https://github.com/example/repo2",
            default_branch="develop",
            language="typescript",
        ),
    ]


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    yield tmp_path


@pytest.mark.asyncio
async def test_clone_single_repo_success(mock_process, temp_dir):
    """Test successful cloning of a single repository."""
    repo = TargetRepo(url="https://github.com/example/test-repo", language="python")
    
    with patch("anyio.run_process", AsyncMock(return_value=mock_process)):
        with patch("shutil.rmtree"):
            repo_dir = await _clone_single_repo(repo, temp_dir)
            
            assert repo_dir == temp_dir / "test-repo"
            
            # Verify that anyio.run_process was called with correct args
            anyio.run_process.assert_called_once()
            call_args = anyio.run_process.call_args[0][0]
            assert "git" in call_args
            assert "clone" in call_args
            assert "--branch" in call_args
            assert "main" in call_args  # Default branch
            assert str(repo.url) in call_args


@pytest.mark.asyncio
async def test_clone_single_repo_failure():
    """Test handling of a failed clone operation with retries."""
    repo = TargetRepo(url="https://github.com/example/invalid-repo", language="python")
    dest_dir = Path("/tmp/test")
    
    # Mock run_process to raise an exception
    error = subprocess.CalledProcessError(1, "git clone")
    error.stderr = b"fatal: repository not found"
    
    with patch("anyio.run_process", AsyncMock(side_effect=error)):
        with patch("shutil.rmtree"):
            # Override retry configuration for testing
            with patch("crawler.clone.retry", lambda **kwargs: lambda f: f):
                with pytest.raises(CloneError) as exc_info:
                    await _clone_single_repo(repo, dest_dir)
                
                assert "Failed to clone" in str(exc_info.value)
                assert "repository not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_clone_repos_concurrent(test_repos, temp_dir):
    """Test concurrent cloning of multiple repositories."""
    with patch("crawler.clone._clone_single_repo", AsyncMock()) as mock_clone:
        # Configure the mock to create directories to simulate successful clones
        async def create_repo_dir(repo, dest_dir):
            repo_url = str(repo.url)
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            repo_dir = dest_dir / repo_name
            repo_dir.mkdir(parents=True, exist_ok=True)
            return repo_dir
        
        mock_clone.side_effect = create_repo_dir
        
        result = await clone_repos(test_repos, temp_dir)
        
        # Verify all repositories were cloned
        assert len(result) == 2
        assert temp_dir / "repo1" in result
        assert temp_dir / "repo2" in result
        
        # Verify _clone_single_repo was called for each repository
        assert mock_clone.call_count == 2 