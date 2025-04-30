"""Initial database schema.

Revision ID: 20250430_initial
Create Date: 2025-04-30 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "20250430_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial tables."""
    # Create action_types enum
    op.execute("CREATE TYPE action_types AS ENUM ('MODIFY', 'CREATE', 'DELETE', 'RENAME', 'MOVE')")

    # Create runs table
    op.create_table(
        "runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repo_path", sa.String(), nullable=False),
        sa.Column("branch", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )

    # Create plan_items table
    op.create_table(
        "plan_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("action", sa.Enum("MODIFY", "CREATE", "DELETE", "RENAME", "MOVE", name="action_types"), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ),
        sa.PrimaryKeyConstraint("id")
    )

    # Create changes table
    op.create_table(
        "changes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("plan_item_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("diff", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("commit_sha", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["plan_item_id"], ["plan_items.id"], ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ),
        sa.PrimaryKeyConstraint("id")
    )

    # Create verifications table
    op.create_table(
        "verifications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("change_id", sa.String(), nullable=False),
        sa.Column("tests_total", sa.Integer(), nullable=False),
        sa.Column("tests_passed", sa.Integer(), nullable=False),
        sa.Column("tests_failed", sa.Integer(), nullable=False),
        sa.Column("tests_skipped", sa.Integer(), nullable=False),
        sa.Column("line_coverage_percent", sa.Float(), nullable=False),
        sa.Column("branch_coverage_percent", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["change_id"], ["changes.id"], ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ),
        sa.PrimaryKeyConstraint("id")
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("verifications")
    op.drop_table("changes")
    op.drop_table("plan_items")
    op.drop_table("runs")
    op.execute("DROP TYPE action_types") 