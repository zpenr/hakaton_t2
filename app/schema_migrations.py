"""Лёгкие правки схемы без Alembic (добавление столбцов в существующую БД)."""

from sqlalchemy import inspect, text

from app.database import engine


def ensure_users_is_approved_column() -> None:
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_approved" in cols:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE users ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1"))
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT true"))
