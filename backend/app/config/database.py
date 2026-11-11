from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL


def _engine_kwargs(url: str) -> dict:
    """
    Connection-pool settings for the engine.

    The pool is PER PROCESS: with N uvicorn workers the app can open up to
    N * (DB_POOL_SIZE + DB_MAX_OVERFLOW) connections (+1 per worker for the
    audit-log writer). Keep that below Postgres' max_connections, leaving
    headroom for migrations, admin tools and other services.
    """
    if url.startswith("sqlite"):
        # SQLite (tests/local) uses its own pool classes; QueuePool args don't apply.
        return {"connect_args": {"check_same_thread": False}}

    kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        # Fail fast (and visibly) instead of hanging a request for 30s when the pool is exhausted.
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        # Recycle before typical LB/RDS idle timeouts silently drop connections.
        "pool_recycle": settings.DB_POOL_RECYCLE,
        # Detect dead connections (DB restart/failover) before handing them out.
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
    }
    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"connect_timeout": settings.DB_CONNECT_TIMEOUT}
    return kwargs


engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs(SQLALCHEMY_DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
