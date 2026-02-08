"""认证路由。"""

from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.api import APIRouter, success_response, error_response
from backend.src.db.session import get_db
from backend.src.models.auth import LoginRequest, TokenResponse
from backend.src.repositories.user import UserRepository
from backend.src.api.deps import SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/auth", tags=["认证"])

TOKEN_EXPIRE_HOURS = 24


def create_access_token(user_id: int, username: str) -> str:
    """生成 JWT Token。"""
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录。"""
    repo = UserRepository(db)
    user = await repo.get_by_username(req.username)

    if user is None or not repo.verify_password(req.password, user.password_hash):
        resp, _ = error_response("用户名或密码错误", "UNAUTHORIZED", 401)
        return resp

    token = create_access_token(user.id, user.username)
    return success_response(
        data=TokenResponse(token=token, username=user.username).model_dump(),
        message="登录成功",
    )
