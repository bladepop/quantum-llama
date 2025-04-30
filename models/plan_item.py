"""Plan item model for code modifications."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic.dataclasses import dataclass


@dataclass
class PlanItem:
    """A planned modification to a code file.

    Attributes:
        id: Unique identifier for the plan item
        file_path: Path to the file to be modified
        action: Type of modification to perform
        reason: Description of why this modification is needed
        confidence: Confidence score between 0 and 1 for this modification
    """

    id: UUID
    file_path: str
    action: Literal["MODIFY", "CREATE", "DELETE", "RENAME", "MOVE"]
    reason: str
    confidence: float  # Between 0 and 1 