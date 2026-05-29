"""Initial schema — all application tables.

Dev shortcut: `create_all()` in app lifespan also works.
Generate fresh revision after model changes:
  alembic revision --autogenerate -m "describe_change"
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables created via Base.metadata.create_all() in dev/tests.
    # This revision marks baseline for Alembic history; autogenerate next diff from models.
    pass


def downgrade() -> None:
    pass
