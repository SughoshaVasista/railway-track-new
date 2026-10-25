"""prevent duplicate open maintenance tasks for an alert

Revision ID: 9a4f14b3c602
Revises: dd787674d8c9
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa


revision = "9a4f14b3c602"
down_revision = "dd787674d8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_maintenance_tasks_alert_open",
        "maintenance_tasks",
        ["alert_id"],
        unique=True,
        sqlite_where=sa.text("status != 'COMPLETED'"),
        postgresql_where=sa.text("status != 'COMPLETED'"),
    )


def downgrade() -> None:
    op.drop_index("uq_maintenance_tasks_alert_open", table_name="maintenance_tasks")
