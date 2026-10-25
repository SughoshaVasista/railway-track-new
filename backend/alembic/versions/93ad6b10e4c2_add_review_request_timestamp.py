"""track when an official returns a task for rework

Revision ID: 93ad6b10e4c2
Revises: 72c14e90a651
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa


revision = "93ad6b10e4c2"
down_revision = "72c14e90a651"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("maintenance_tasks")}
    if "review_requested_at" not in columns:
        op.add_column("maintenance_tasks", sa.Column("review_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("maintenance_tasks")}
    if "review_requested_at" in columns:
        op.drop_column("maintenance_tasks", "review_requested_at")
