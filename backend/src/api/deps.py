"""FastAPI 依赖注入。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.session import get_db
from backend.src.repositories.user import UserRepository

security = HTTPBearer(auto_error=False)

# 从 settings 中读取（在 main.py 初始化后可用）
SECRET_KEY = "dev-secret-key-change-in-production"
ALGORITHM = "HS256"


def set_secret_key(key: str):
    """由 main.py 在启动时调用，设置 JWT 密钥。"""
    global SECRET_KEY
    SECRET_KEY = key


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """从 JWT Token 解析当前用户。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的 Token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 已过期或无效")

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
