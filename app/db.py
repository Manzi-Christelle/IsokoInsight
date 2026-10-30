from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema(bind=engine) -> None:
    """Small, explicit migration for databases created before accounts had roles and approval.

    create_all() does not add columns to existing tables, so the missing columns are added here.
    Old 'contributor' accounts become 'farmer_seller' accounts.
    """
    insp = inspect(bind)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    statements = []
    if "full_name" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(200)")
    if "organisation" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN organisation VARCHAR(200)")
    if "status" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
    with bind.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        if "role" in cols:
            conn.execute(text("UPDATE users SET role = 'farmer_seller' WHERE role = 'contributor'"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
