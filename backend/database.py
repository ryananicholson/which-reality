import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings


def _build_url() -> str:
    """
    Use DATABASE_URL (PostgreSQL) when provided — this is the persistent store on Render.
    Fall back to SQLite for local development.

    Checks os.environ first, then pydantic settings (which also reads env vars),
    so it works regardless of how the variable is injected.
    """
    # Primary: raw os.environ (always reflects Render/system env vars at startup)
    database_url = os.environ.get("DATABASE_URL", "").strip()

    # Secondary: pydantic settings value (also reads env vars, belt-and-suspenders)
    if not database_url:
        database_url = (settings.database_url or "").strip()

    if database_url:
        # Render Postgres gives postgres:// but SQLAlchemy needs postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    # Local dev: SQLite
    path = settings.db_path
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return f"sqlite:///{path}"


_url = _build_url()
_is_postgres = _url.startswith("postgresql")

engine = create_engine(
    _url,
    **({"pool_pre_ping": True, "pool_recycle": 300} if _is_postgres else {"connect_args": {"check_same_thread": False}}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import logging
    _log = logging.getLogger(__name__)

    # Diagnostic: show what DATABASE_URL was found (first 30 chars only)
    _raw_env = os.environ.get("DATABASE_URL", "")
    if _raw_env:
        _log.info("DATABASE: DATABASE_URL env var found, starts with: %s...", _raw_env[:30])
    else:
        _log.warning("DATABASE: DATABASE_URL env var is NOT set in os.environ")

    if _is_postgres:
        _log.info("DATABASE: connected to PostgreSQL (Neon) — data is persistent ✓")
    else:
        _log.warning(
            "DATABASE: using SQLite at %s — data will be lost on redeploy! "
            "Set DATABASE_URL=postgresql://... in your Render environment variables.",
            _url,
        )

    from models import recommendation, wheel, account, watchlist, champion  # noqa: F401
    Base.metadata.create_all(bind=engine)
    try:
        _migrate_add_columns()
    except Exception as e:
        _log.warning("Column migration skipped: %s", e)


def _migrate_add_columns():
    """Safely add new columns to existing tables without dropping data."""
    from sqlalchemy import text
    additions = [
        ("wheel_recommendations", "assignment_chance_pct", "FLOAT"),
        ("wheel_recommendations", "assignment_risk",       "VARCHAR(10)"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in additions:
            try:
                if _is_postgres:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                    ))
                else:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                    ))
                conn.commit()
            except Exception:
                conn.rollback()
