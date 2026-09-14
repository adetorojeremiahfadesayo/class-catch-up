"""Add teacher introduction and territory-aware class settings."""

from alembic import op
import sqlalchemy as sa


revision = "0006_territory_onboarding"
down_revision = "0005_student_exceptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("introduction", sa.String(500)))
    op.add_column("users", sa.Column("selected_class_id", sa.String(36)))
    op.add_column("classes", sa.Column("education_system", sa.String(50)))
    op.add_column("classes", sa.Column("level_label", sa.String(50)))


def downgrade() -> None:
    op.drop_column("classes", "level_label")
    op.drop_column("classes", "education_system")
    op.drop_column("users", "selected_class_id")
    op.drop_column("users", "introduction")
