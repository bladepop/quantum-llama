"""Tests for the TargetRepo model."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.target_repo import TargetRepo


def test_target_repo_valid_creation() -> None:
    """Test creating a TargetRepo with valid data."""
    repo = TargetRepo(
        url="https://github.com/example/repo",
        language="python",
    )
    assert repo.url == "https://github.com/example/repo"
    assert repo.default_branch == "main"  # default value
    assert repo.language == "python"


def test_target_repo_custom_branch() -> None:
    """Test creating a TargetRepo with a custom default branch."""
    repo = TargetRepo(
        url="https://github.com/example/repo",
        default_branch="master",
        language="typescript",
    )
    assert repo.default_branch == "master"
    assert repo.language == "typescript"


def test_target_repo_invalid_url() -> None:
    """Test that invalid URLs are rejected."""
    with pytest.raises(ValidationError):
        TargetRepo(
            url="not-a-url",
            language="python",
        )


def test_target_repo_invalid_language() -> None:
    """Test that invalid languages are rejected."""
    with pytest.raises(ValidationError):
        TargetRepo(
            url="https://github.com/example/repo",
            language="ruby",  # type: ignore
        ) 