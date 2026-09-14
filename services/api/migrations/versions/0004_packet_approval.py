"""Add agent runs, packet revisions, assignments, and exceptions."""

from alembic import op
import sqlalchemy as sa


revision = "0004_packet_approval"
down_revision = "0003_daily_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lesson_occurrences.id"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("packet_jobs.id"), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_agent_runs_scope", "agent_runs", ["tenant_id", "lesson_id"]
    )
    op.create_table(
        "packet_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lesson_occurrences.id"),
            nullable=False,
        ),
        sa.Column("lesson_revision", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("packet_revisions.id")),
        sa.Column("material_version_ids", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("approved_hash", sa.String(64)),
        sa.Column("generation_run_id", sa.String(36), sa.ForeignKey("agent_runs.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "lesson_id", "revision_number"),
    )
    op.create_index(
        "ix_packet_revisions_scope", "packet_revisions", ["tenant_id", "lesson_id"]
    )
    op.create_table(
        "assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lesson_occurrences.id"),
            nullable=False,
        ),
        sa.Column(
            "packet_revision_id",
            sa.String(36),
            sa.ForeignKey("packet_revisions.id"),
            nullable=False,
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "student_id", "lesson_id", "packet_revision_id"
        ),
    )
    op.create_index(
        "ix_assignments_student",
        "assignments",
        ["tenant_id", "student_id", "superseded_at"],
    )
    op.create_table(
        "exceptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("student_id", sa.String(36)),
        sa.Column(
            "lesson_id", sa.String(36), sa.ForeignKey("lesson_occurrences.id")
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("open", sa.Boolean(), nullable=False),
        sa.Column("source_event_id", sa.String(36)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_exceptions_scope", "exceptions", ["tenant_id", "class_id", "open"]
    )


def downgrade() -> None:
    op.drop_table("exceptions")
    op.drop_table("assignments")
    op.drop_table("packet_revisions")
    op.drop_table("agent_runs")
