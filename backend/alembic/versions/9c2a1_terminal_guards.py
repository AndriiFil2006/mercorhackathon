"""Guard immutable terminal generations in SQLite."""
from alembic import op
revision = "9c2a1"
down_revision = "413a9d27174c"
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""
                CREATE TRIGGER generations_no_{action.lower()} BEFORE {action} ON generations
                WHEN OLD.status IN ('completed', 'failed')
                BEGIN SELECT RAISE(ABORT, 'Terminal generations are immutable'); END
            """)

def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS generations_no_update")
        op.execute("DROP TRIGGER IF EXISTS generations_no_delete")

