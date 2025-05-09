"""Git operations helper for managing branches and pull requests."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import pygit2
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PullRequest(BaseModel):
    """Model representing a GitHub pull request."""

    number: int = Field(description="PR number")
    url: str = Field(description="PR URL")
    title: str = Field(description="PR title")
    body: str = Field(description="PR description")
    head: str = Field(description="Head branch name")
    base: str = Field(description="Base branch name")
    reviewers: List[str] = Field(default_factory=list, description="Assigned reviewers")


class GitOps:
    """Helper class for Git operations using pygit2."""

    def __init__(
        self,
        repo_path: str | Path,
        github_token: Optional[str] = None,
        committer: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize GitOps with repository path and credentials.
        
        Args:
            repo_path: Path to the Git repository
            github_token: Optional GitHub personal access token for API operations
            committer: Optional dictionary with 'name' and 'email' for commits
        """
        self.repo_path = Path(repo_path)
        self.repo = pygit2.Repository(str(self.repo_path))
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        
        if not self.github_token:
            logger.warning("No GitHub token provided, PR operations will be unavailable")
        
        self.committer = committer or {
            "name": "Quantum Llama",
            "email": "bot@quantum-llama.ai"
        }

    def create_branch(self, branch_name: str, from_ref: str = "HEAD") -> pygit2.Reference:
        """Create a new branch from the specified reference.
        
        Args:
            branch_name: Name of the branch to create
            from_ref: Reference to create branch from (default: HEAD)
        
        Returns:
            The newly created branch reference
        
        Raises:
            ValueError: If branch already exists or reference is invalid
        """
        try:
            ref = self.repo.references[from_ref]
            if not ref:
                raise ValueError(f"Reference {from_ref} not found")

            if f"refs/heads/{branch_name}" in self.repo.references:
                raise ValueError(f"Branch {branch_name} already exists")

            new_branch = self.repo.branches.create(branch_name, ref.peel())
            logger.info(f"Created branch {branch_name} from {from_ref}")
            return new_branch

        except (KeyError, pygit2.GitError) as e:
            raise ValueError(f"Failed to create branch: {e}") from e

    def checkout_branch(self, branch_name: str) -> None:
        """Checkout the specified branch.
        
        Args:
            branch_name: Name of the branch to checkout
        
        Raises:
            ValueError: If branch doesn't exist or checkout fails
        """
        try:
            branch_ref = self.repo.references[f"refs/heads/{branch_name}"]
            self.repo.checkout(branch_ref)
            logger.info(f"Checked out branch {branch_name}")

        except (KeyError, pygit2.GitError) as e:
            raise ValueError(f"Failed to checkout branch: {e}") from e

    def commit_changes(
        self, message: str, files: Optional[List[str]] = None
    ) -> Optional[str]:
        """Create a commit with the specified changes.
        
        Args:
            message: Commit message
            files: Optional list of files to commit. If None, commits all changes.
        
        Returns:
            The commit hash if successful, None if no changes to commit
        
        Raises:
            ValueError: If commit operation fails
        """
        try:
            # Get repository index
            index = self.repo.index
            
            # Stage specific files or all changes
            if files:
                for file_path in files:
                    index.add(file_path)
            else:
                index.add_all()
            
            # Check if there are changes to commit
            diff = self.repo.diff()
            if not diff:
                logger.info("No changes to commit")
                return None
            
            # Write tree and create commit
            tree_id = index.write_tree()
            index.write()
            
            # Get parent commit
            parent = self.repo.head.peel()
            
            # Create commit
            commit_id = self.repo.create_commit(
                "HEAD",
                self.committer,  # author
                self.committer,  # committer
                message,
                tree_id,
                [parent.id]
            )
            
            logger.info(f"Created commit {commit_id}")
            return str(commit_id)

        except pygit2.GitError as e:
            raise ValueError(f"Failed to create commit: {e}") from e

    def push_branch(self, branch_name: str, remote_name: str = "origin") -> None:
        """Push a branch to the remote repository.
        
        Args:
            branch_name: Name of the branch to push
            remote_name: Name of the remote to push to (default: origin)
            
        Raises:
            ValueError: If push fails or branch doesn't exist
        """
        try:
            # Get the remote
            remote = self.repo.remotes[remote_name]
            if not remote:
                raise ValueError(f"Remote {remote_name} not found")

            # Push using git command (pygit2 push requires more complex auth setup)
            import subprocess
            result = subprocess.run(
                ["git", "push", remote_name, branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise ValueError(f"Push failed: {result.stderr}")
            
            logger.info(f"Pushed branch {branch_name} to {remote_name}")

        except (KeyError, pygit2.GitError, subprocess.CalledProcessError) as e:
            raise ValueError(f"Failed to push branch: {e}")

    def get_codeowners_for_path(self, file_path: str) -> List[str]:
        """Get reviewers from CODEOWNERS file for a given path.
        
        Args:
            file_path: Path to the file to get reviewers for
            
        Returns:
            List of GitHub usernames/teams that should review changes to this path
        """
        codeowners_path = self.repo_path / ".github" / "CODEOWNERS"
        if not codeowners_path.exists():
            logger.warning("CODEOWNERS file not found")
            return []

        reviewers = []
        file_path = str(file_path)

        try:
            with open(codeowners_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Split into pattern and owners
                    parts = line.split()
                    if len(parts) < 2:
                        continue

                    pattern = parts[0]
                    owners = parts[1:]

                    # Convert pattern to regex
                    import fnmatch
                    if fnmatch.fnmatch(file_path, pattern):
                        reviewers.extend(owners)

            # Remove duplicates while preserving order
            seen = set()
            unique_reviewers = []
            for reviewer in reviewers:
                if reviewer not in seen:
                    seen.add(reviewer)
                    unique_reviewers.append(reviewer)

            return unique_reviewers

        except Exception as e:
            logger.error(f"Error reading CODEOWNERS: {e}")
            return []

    def generate_pr_checklist(self, files_changed: List[str]) -> str:
        """Generate a markdown checklist for the PR description.
        
        Args:
            files_changed: List of files that were changed
            
        Returns:
            Markdown formatted checklist
        """
        checklist = [
            "## Changes",
            "This PR includes the following changes:",
            ""
        ]
        
        for file in sorted(files_changed):
            checklist.append(f"- [ ] {file}")
        
        checklist.extend([
            "",
            "## Checklist",
            "- [ ] Tests added/updated and passing",
            "- [ ] Documentation updated",
            "- [ ] Code follows project conventions",
            "- [ ] Commit messages follow conventional commits format",
            "- [ ] CI checks passing",
            "",
            "## Reviewers",
            "Please review the changes according to:",
            "- Code quality and style",
            "- Test coverage",
            "- Documentation completeness",
            "- Security implications"
        ])
        
        return "\n".join(checklist)

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        reviewers: Optional[List[str]] = None,
        files_changed: Optional[List[str]] = None,
    ) -> PullRequest:
        """Create a GitHub pull request.
        
        Args:
            title: PR title
            body: PR description
            head_branch: Source branch name
            base_branch: Target branch name (default: main)
            reviewers: Optional list of GitHub usernames to request review from
            files_changed: Optional list of changed files to include in checklist
        
        Returns:
            PullRequest object with PR details
        
        Raises:
            ValueError: If PR creation fails or GitHub token is missing
        """
        if not self.github_token:
            raise ValueError("GitHub token required for PR operations")

        try:
            # Extract owner and repo from remote URL
            remote_url = self.repo.remotes["origin"].url
            parsed_url = urlparse(remote_url)
            path_parts = parsed_url.path.strip("/").split("/")
            owner, repo = path_parts[0], path_parts[1].replace(".git", "")

            # Add checklist to PR body if files were changed
            if files_changed:
                body = f"{body}\n\n{self.generate_pr_checklist(files_changed)}"

            # Prepare PR data
            pr_data = {
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch
            }

            # Create PR using GitHub API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls",
                    json=pr_data,
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )
                response.raise_for_status()
                pr_info = response.json()

                # Get reviewers from CODEOWNERS if not specified
                if not reviewers and files_changed:
                    reviewers = []
                    for file in files_changed:
                        reviewers.extend(self.get_codeowners_for_path(file))

                # Request reviews if specified
                if reviewers:
                    await client.post(
                        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_info['number']}/requested_reviewers",
                        json={"reviewers": reviewers},
                        headers={
                            "Authorization": f"token {self.github_token}",
                            "Accept": "application/vnd.github.v3+json"
                        }
                    )

                logger.info(
                    f"Created PR #{pr_info['number']}: {title}",
                    extra={
                        "pr_url": pr_info["html_url"],
                        "reviewers": reviewers
                    }
                )

                return PullRequest(
                    number=pr_info["number"],
                    url=pr_info["html_url"],
                    title=pr_info["title"],
                    body=pr_info["body"],
                    head=pr_info["head"]["ref"],
                    base=pr_info["base"]["ref"],
                    reviewers=reviewers or []
                )

        except (httpx.HTTPError, KeyError) as e:
            raise ValueError(f"Failed to create pull request: {e}") from e 