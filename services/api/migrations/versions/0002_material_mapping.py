"""Add materials, segments, topics, timetable, and mappings."""

from alembic import op
import sqlalchemy as sa


revision = "0002_material_mapping"
down_revision = "0001_foundations"
branch_labels = None
depends_on = None


def owned_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.id"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "materials",
        *owned_columns(),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("extraction_status", sa.String(20), nullable=False),
        sa.Column("extraction_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "class_id", "content_hash", "version"),
    )
    op.create_index("ix_materials_scope", "materials", ["tenant_id", "class_id"])
    op.create_table(
        "segments",
        *owned_columns(),
        sa.Column(
            "material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_1_based", sa.Integer()),
        sa.Column("text_section", sa.String(100)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("material_id", "position"),
    )
    op.create_index(
        "ix_segments_scope", "segments", ["tenant_id", "class_id", "material_id"]
    )
    op.create_table(
        "topics",
        *owned_columns(),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "class_id", "title"),
    )
    op.create_index("ix_topics_scope", "topics", ["tenant_id", "class_id"])
    op.create_table(
        "timetable_slots",
        *owned_columns(),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(100), nullable=False),
        sa.Column("start_local", sa.Time(), nullable=False),
        sa.Column("end_local", sa.Time(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "class_id", "weekday", "period_key", "effective_from"
        ),
    )
    op.create_index(
        "ix_timetable_scope", "timetable_slots", ["tenant_id", "class_id"]
    )
    op.create_table(
        "mapping_proposals",
        *owned_columns(),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("suggested_segment_ids", sa.JSON(), nullable=False),
        sa.Column("approved_segment_ids", sa.JSON(), nullable=False),
        sa.Column("unmatched", sa.Boolean(), nullable=False),
        sa.Column("proposal_method", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "class_id", "topic_id"),
    )
    op.create_index(
        "ix_mapping_proposals_scope", "mapping_proposals", ["tenant_id", "class_id"]
    )


def downgrade() -> None:
    op.drop_table("mapping_proposals")
    op.drop_table("timetable_slots")
    op.drop_table("topics")
    op.drop_table("segments")
    op.drop_table("materials")
