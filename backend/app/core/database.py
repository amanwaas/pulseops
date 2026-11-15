from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

Base = declarative_base()

# Format connection string for asyncpg
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configure Neon Serverless / PgBouncer specific options
connect_args = {}
engine_kwargs = {
    "echo": False,
    "future": True,
}

if "asyncpg" in db_url:
    # 1. Disable prepared statement cache for Neon PgBouncer transaction pooling
    connect_args["statement_cache_size"] = 0

    # 2. Parse and clean query params because asyncpg does not accept sslmode/channel_binding in query string
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)

    needs_ssl = "neon.tech" in db_url or "sslmode" in query_params or "ssl" in query_params
    if needs_ssl:
        connect_args["ssl"] = "require"

    # Remove sslmode, channel_binding, etc. from query string so asyncpg doesn't error out
    cleaned_query = {k: v for k, v in query_params.items() if k not in ["sslmode", "channel_binding", "ssl"]}
    new_query_str = urlencode({k: v[0] for k, v in cleaned_query.items()}) if cleaned_query else ""
    db_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query_str, parsed.fragment))

    import os
    if os.getenv("TESTING") == "1" or settings.ENVIRONMENT == "testing":
        from sqlalchemy.pool import NullPool
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = connect_args
    else:
        engine_kwargs.update({
            "connect_args": connect_args,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
        })
elif "sqlite" in db_url:
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initializes schema if tables do not exist (useful for testing or first run)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
