"""认证相关 Pydantic 模型。"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求。"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """登录成功响应。"""
    token: str
    username: str
