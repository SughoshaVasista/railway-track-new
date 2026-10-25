"""allow maintenance tasks to remain open without a worker

Revision ID: 4b7c1a2d9e31
Revises: 9a4f14b3c602
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa


revision = "4b7c1a2d9e31"
down_revision = "9a4f14b3c602"
branch_labels = None
depends_on = None

FK_NAME = "fk_maintenance_tasks_assigned_worker_user_id_users"
NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("maintenance_tasks", naming_convention=NAMING) as batch:
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.alter_column(
            "assigned_worker_user_id",
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch.create_foreign_key(FK_NAME, "users", ["assigned_worker_user_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM maintenance_tasks WHERE assigned_worker_user_id IS NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while maintenance tasks are unassigned")
    with op.batch_alter_table("maintenance_tasks", naming_convention=NAMING) as batch:
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.alter_column(
            "assigned_worker_user_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch.create_foreign_key(FK_NAME, "users", ["assigned_worker_user_id"], ["id"], ondelete="RESTRICT")
