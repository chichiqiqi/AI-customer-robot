"""数据库会话管理。"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 全局引擎和会话工厂（在 main.py 中初始化）
engine = None
async_session_factory = None


def init_engine(database_url: str, echo: bool = False):
    """初始化数据库引擎。"""
    global engine, async_session_factory
    engine = create_async_engine(database_url, echo=echo)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db():
    """FastAPI 依赖：获取数据库会话。"""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_engine() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
