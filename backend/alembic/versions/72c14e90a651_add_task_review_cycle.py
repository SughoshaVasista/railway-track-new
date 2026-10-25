"""add worker submission and official task review cycle

Revision ID: 72c14e90a651
Revises: 4b7c1a2d9e31
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa


revision = "72c14e90a651"
down_revision = "4b7c1a2d9e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("maintenance_tasks") as batch:
        batch.drop_constraint("ck_tasks_status", type_="check")
        batch.create_check_constraint(
            "ck_tasks_status",
            "status IN ('ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'AWAITING_REVIEW', 'COMPLETED')",
        )
        batch.add_column(sa.Column("review_status", sa.String(length=24), nullable=True))
        batch.add_column(sa.Column("review_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM maintenance_tasks WHERE status = 'AWAITING_REVIEW' LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while tasks are awaiting review")
    with op.batch_alter_table("maintenance_tasks") as batch:
        batch.drop_column("review_notes")
        batch.drop_column("review_status")
        batch.drop_constraint("ck_tasks_status", type_="check")
        batch.create_check_constraint(
            "ck_tasks_status",
            "status IN ('ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'COMPLETED')",
        )
