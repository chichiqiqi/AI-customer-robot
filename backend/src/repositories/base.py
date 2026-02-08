"""Repository 基类。"""

from typing import TypeVar, Generic, Optional, Type

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """通用数据访问基类。"""

    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    async def get_by_id(self, id: int) -> Optional[T]:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def create(self, obj: T) -> T:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        result = await self.db.execute(
            sa_delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
