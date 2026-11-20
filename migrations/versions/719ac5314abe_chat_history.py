"""Store assistant conversations per account."""
from alembic import op
import sqlalchemy as sa

revision = "719ac5314abe"
down_revision = "3dfb67eddef4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("chat_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("thread", sa.String(32), nullable=False),
        sa.Column("first_turn", sa.Boolean(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False))
    op.create_index("ix_chat_turn_owner_thread", "chat_turns", ["user_id", "thread", "id"])


def downgrade():
    op.drop_table("chat_turns")
