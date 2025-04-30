"""OpenAI function schemas for structured output."""
from __future__ import annotations

from typing import Any, Dict

PLAN_ITEM_SCHEMA: Dict[str, Any] = {
    "name": "create_plan_item",
    "description": "Create a plan item for a code modification",
    "parameters": {
        "type": "object",
        "required": ["file_path", "action", "reason", "confidence"],
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to be modified, relative to repository root"
            },
            "action": {
                "type": "string",
                "enum": ["MODIFY", "CREATE", "DELETE", "RENAME", "MOVE"],
                "description": "Type of modification to perform on the file"
            },
            "reason": {
                "type": "string",
                "description": "Detailed explanation of why this modification is needed"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score between 0 and 1 for this modification"
            }
        }
    }
}

def get_plan_item_schema() -> Dict[str, Any]:
    """Get the OpenAI function schema for PlanItem creation.
    
    Returns:
        Dict containing the function schema that can be passed to OpenAI's
        function calling API.
    """
    return PLAN_ITEM_SCHEMA 