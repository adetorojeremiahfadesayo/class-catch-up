"""Add student progress, attempts, and assignment help state."""

from alembic import op
import sqlalchemy as sa


revision = "0005_student_exceptions"
down_revision = "0004_packet_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("help_requested", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "progress_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "assignment_id",
            sa.String(36),
            sa.ForeignKey("assignments.id"),
            nullable=False,
        ),
        sa.Column("step_id", sa.String(100), nullable=False),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_progress_assignment",
        "progress_events",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_table(
        "attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "assignment_id",
            sa.String(36),
            sa.ForeignKey("assignments.id"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(100), nullable=False),
        sa.Column("answer", sa.String(100), nullable=False),
        sa.Column("correctness", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_attempts_assignment",
        "attempts",
        ["tenant_id", "assignment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("progress_events")
    op.drop_column("assignments", "help_requested")
