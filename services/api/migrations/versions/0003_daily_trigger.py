"""Add lesson, attendance, durable job, idempotency, and audit tables."""

from alembic import op
import sqlalchemy as sa


revision = "0003_daily_trigger"
down_revision = "0002_material_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_occurrences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("period_key", sa.String(100), nullable=False),
        sa.Column("planned_topic_ids", sa.JSON(), nullable=False),
        sa.Column("actual_topic_ids", sa.JSON(), nullable=False),
        sa.Column("segment_ids", sa.JSON(), nullable=False),
        sa.Column("coverage_status", sa.String(30), nullable=False),
        sa.Column("moved_to_date", sa.Date()),
        sa.Column("moved_to_period_key", sa.String(100)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "class_id", "local_date", "period_key"),
    )
    op.create_index(
        "ix_lesson_occurrences_lookup",
        "lesson_occurrences",
        ["tenant_id", "class_id", "local_date", "period_key"],
    )
    op.create_table(
        "attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lesson_occurrences.id"),
            nullable=False,
        ),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "lesson_id", "student_id"),
    )
    op.create_index(
        "ix_attendance_scope",
        "attendance",
        ["tenant_id", "lesson_id", "student_id"],
    )
    op.create_table(
        "packet_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "lesson_id",
            sa.String(36),
            sa.ForeignKey("lesson_occurrences.id"),
            nullable=False,
        ),
        sa.Column("lesson_revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("idempotency_key", sa.String(250), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
    )
    op.create_index("ix_packet_jobs_claim", "packet_jobs", ["state", "lease_until"])
    op.create_table(
        "idempotency_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(200), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "actor_id", "request_key"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id")),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("source_event_id", sa.String(36)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_events_scope", "audit_events", ["tenant_id", "class_id"]
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("idempotency_receipts")
    op.drop_table("packet_jobs")
    op.drop_table("attendance")
    op.drop_table("lesson_occurrences")
