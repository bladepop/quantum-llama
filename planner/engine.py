"""Planner engine for analyzing repository snapshots and generating plan items."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import jinja2
from openai import AsyncOpenAI
from pydantic import ValidationError

from models.plan_item import PlanItem
from llm.schema import get_plan_item_schema

logger = logging.getLogger(__name__)

class PlannerEngine:
    """Engine for analyzing repository snapshots and generating plan items."""

    def __init__(self, openai_client: Optional[AsyncOpenAI] = None) -> None:
        """Initialize the planner engine.
        
        Args:
            openai_client: Optional OpenAI client instance. If not provided,
                         a new client will be created.
        """
        self.openai_client = openai_client or AsyncOpenAI()
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader("prompts"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def plan_repo(self, repo_snapshot: Dict[str, Any]) -> List[PlanItem]:
        """Analyze a repository snapshot and generate plan items.
        
        Args:
            repo_snapshot: Dictionary containing repository analysis data including:
                         - files: List of file paths
                         - asts: Dictionary mapping file paths to their AST data
                         - metrics: Repository-wide metrics (test coverage, etc.)
        
        Returns:
            List of PlanItem instances representing suggested modifications.
        
        Raises:
            ValueError: If the snapshot format is invalid
            ValidationError: If generated plan items fail validation
        """
        if not isinstance(repo_snapshot, dict):
            raise ValueError("Repo snapshot must be a dictionary")

        files = repo_snapshot.get("files", [])
        asts = repo_snapshot.get("asts", {})
        metrics = repo_snapshot.get("metrics", {})

        plan_items: List[PlanItem] = []

        # Process each file in the snapshot
        for file_path in files:
            ast_data = asts.get(file_path)
            if not ast_data:
                logger.warning(f"No AST data found for {file_path}")
                continue

            # Select appropriate template based on file analysis
            template_name = self._select_template(file_path, ast_data, metrics)
            if not template_name:
                continue

            # Render prompt and call OpenAI
            prompt = self._render_prompt(template_name, {
                "file_path": file_path,
                "reason": self._generate_reason(file_path, ast_data, metrics)
            })

            try:
                completion = await self.openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    functions=[get_plan_item_schema()],
                    function_call={"name": "create_plan_item"}
                )

                # Parse function call result
                if completion.choices[0].message.function_call:
                    args = json.loads(completion.choices[0].message.function_call.arguments)
                    plan_item = PlanItem(
                        id=uuid4(),
                        file_path=args["file_path"],
                        action=args["action"],
                        reason=args["reason"],
                        confidence=args["confidence"]
                    )
                    plan_items.append(plan_item)

            except (ValidationError, json.JSONDecodeError) as e:
                logger.error(f"Failed to create plan item for {file_path}: {e}")
                continue

        return plan_items

    def _select_template(
        self, file_path: str, ast_data: Dict[str, Any], metrics: Dict[str, Any]
    ) -> Optional[str]:
        """Select the most appropriate template for a file.
        
        Args:
            file_path: Path to the file being analyzed
            ast_data: AST data for the file
            metrics: Repository-wide metrics
        
        Returns:
            Template name if a suitable template is found, None otherwise
        """
        # Simple template selection logic - can be enhanced based on metrics
        if "test" in metrics.get("needs_improvement", []):
            return "add_tests.j2"
        elif any(dep in metrics.get("outdated_deps", []) for dep in ast_data.get("imports", [])):
            return "upgrade_runtime.j2"
        elif ast_data.get("complexity", 0) > metrics.get("max_complexity", 10):
            return "refactor.j2"
        return None

    def _generate_reason(
        self, file_path: str, ast_data: Dict[str, Any], metrics: Dict[str, Any]
    ) -> str:
        """Generate a reason for modifying a file.
        
        Args:
            file_path: Path to the file being analyzed
            ast_data: AST data for the file
            metrics: Repository-wide metrics
        
        Returns:
            String explaining why the file needs modification
        """
        # Simple reason generation - can be enhanced with more metrics
        if "test" in metrics.get("needs_improvement", []):
            return f"Add test coverage for {Path(file_path).stem}"
        elif ast_data.get("complexity", 0) > metrics.get("max_complexity", 10):
            return f"Reduce complexity in {Path(file_path).stem}"
        elif any(dep in metrics.get("outdated_deps", []) for dep in ast_data.get("imports", [])):
            return f"Update dependencies in {Path(file_path).stem}"
        return "General code improvement"

    def _render_prompt(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a prompt template with the given context.
        
        Args:
            template_name: Name of the template file
            context: Dictionary of variables to pass to the template
        
        Returns:
            Rendered prompt string
        """
        template = self.jinja_env.get_template(template_name)
        return template.render(**context) 