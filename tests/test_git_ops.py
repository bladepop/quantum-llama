"""Tests for the git operations helper."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pygit2
import pytest

from engine.git_ops import GitOps, PullRequest


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Git repository for testing.
    
    Args:
        tmp_path: Pytest temporary directory fixture
    
    Yields:
        Path to the temporary repository
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Initialize repository
    repo = pygit2.init_repository(str(repo_path))
    
    # Create initial commit
    index = repo.index
    
    # Create a test file
    test_file = repo_path / "test.txt"
    test_file.write_text("test content")
    
    # Stage and commit
    index.add("test.txt")
    tree_id = index.write_tree()
    author = pygit2.Signature("Test User", "test@example.com")
    repo.create_commit(
        "HEAD",
        author,
        author,
        "Initial commit",
        tree_id,
        []
    )
    
    # Add remote
    repo.remotes.create(
        "origin",
        "https://github.com/test-org/test-repo.git"
    )
    
    yield repo_path


@pytest.fixture
def git_ops(temp_git_repo: Path) -> GitOps:
    """Create a GitOps instance with a temporary repository.
    
    Args:
        temp_git_repo: Temporary repository fixture
    
    Returns:
        Configured GitOps instance
    """
    return GitOps(
        repo_path=temp_git_repo,
        github_token="test-token",
        committer={
            "name": "Test User",
            "email": "test@example.com"
        }
    )


def test_create_branch(git_ops: GitOps) -> None:
    """Test branch creation."""
    branch = git_ops.create_branch("test-branch")
    assert branch.name == "test-branch"
    assert "refs/heads/test-branch" in git_ops.repo.references

    # Test creating from existing branch
    other_branch = git_ops.create_branch("other-branch", "refs/heads/test-branch")
    assert other_branch.name == "other-branch"
    
    # Test invalid reference
    with pytest.raises(ValueError, match="Reference invalid-ref not found"):
        git_ops.create_branch("new-branch", "invalid-ref")
    
    # Test duplicate branch
    with pytest.raises(ValueError, match="Branch test-branch already exists"):
        git_ops.create_branch("test-branch")


def test_checkout_branch(git_ops: GitOps) -> None:
    """Test branch checkout."""
    # Create and checkout branch
    git_ops.create_branch("test-branch")
    git_ops.checkout_branch("test-branch")
    
    assert git_ops.repo.head.name == "refs/heads/test-branch"
    
    # Test invalid branch
    with pytest.raises(ValueError, match="Failed to checkout branch"):
        git_ops.checkout_branch("invalid-branch")


def test_commit_changes(git_ops: GitOps, temp_git_repo: Path) -> None:
    """Test committing changes."""
    # Create test file
    test_file = temp_git_repo / "new_file.txt"
    test_file.write_text("new content")
    
    # Commit specific file
    commit_id = git_ops.commit_changes(
        "Add new file",
        files=["new_file.txt"]
    )
    assert commit_id is not None
    
    # Verify commit
    commit = git_ops.repo.get(pygit2.Oid(hex=commit_id))
    assert commit.message == "Add new file"
    assert "new_file.txt" in git_ops.repo.head.peel().tree
    
    # Test commit with no changes
    assert git_ops.commit_changes("No changes") is None


@pytest.mark.asyncio
async def test_create_pull_request(git_ops: GitOps) -> None:
    """Test pull request creation."""
    # Mock HTTP responses
    mock_pr_response = {
        "number": 1,
        "html_url": "https://github.com/test-org/test-repo/pull/1",
        "title": "Test PR",
        "body": "Test description",
        "head": {"ref": "test-branch"},
        "base": {"ref": "main"}
    }
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock()
        mock_client.return_value.__aenter__.return_value.post.return_value.json.return_value = mock_pr_response
        mock_client.return_value.__aenter__.return_value.post.return_value.raise_for_status = MagicMock()
        
        pr = await git_ops.create_pull_request(
            title="Test PR",
            body="Test description",
            head_branch="test-branch",
            base_branch="main",
            reviewers=["test-user"]
        )
        
        assert isinstance(pr, PullRequest)
        assert pr.number == 1
        assert pr.title == "Test PR"
        assert pr.head == "test-branch"
        assert pr.base == "main"
        
        # Verify API calls
        mock_client.return_value.__aenter__.return_value.post.assert_any_call(
            "https://api.github.com/repos/test-org/test-repo/pulls",
            json={
                "title": "Test PR",
                "body": "Test description",
                "head": "test-branch",
                "base": "main"
            },
            headers={
                "Authorization": "token test-token",
                "Accept": "application/vnd.github.v3+json"
            }
        )


def test_git_ops_no_token() -> None:
    """Test GitOps initialization without GitHub token."""
    with patch.dict(os.environ, clear=True):
        ops = GitOps("dummy/path")
        assert ops.github_token is None
        
        with pytest.raises(ValueError, match="GitHub token required"):
            pytest.mark.asyncio(ops.create_pull_request(
                "title", "body", "head", "base"
            )) 