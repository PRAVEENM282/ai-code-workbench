from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench.infrastructure.settings import DatabaseSettings


def make_session_factory(settings: DatabaseSettings, engine=None) -> async_sessionmaker:
    if engine is None:
        engine = create_async_engine(
            settings.url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            connect_args={"timeout": settings.connect_timeout_seconds},
        )
    return async_sessionmaker(engine, expire_on_commit=False)
