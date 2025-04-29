"""Target repository model for code analysis and operations."""
from __future__ import annotations

from typing import Literal

from pydantic import HttpUrl
from pydantic.dataclasses import dataclass


@dataclass
class TargetRepo:
    """Repository to analyze and potentially modify.

    Attributes:
        url: Git repository URL
        default_branch: Default branch to use, defaults to 'main'
        language: Primary programming language of the repository
    """

    url: HttpUrl
    default_branch: str = "main"
    language: Literal["python", "typescript", "java", "go"] 