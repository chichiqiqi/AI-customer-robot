"""应用入口。"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中，使 pycore 和 backend 可导入
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pycore.core import Logger, LoggerConfig, LogLevel, get_logger, ConfigManager
from pycore.api import APIServer, APIConfig

from backend.src.config.settings import AppSettings, LLMSettings, EmbeddingSettings, RetrievalSettings
from backend.src.db.session import init_engine, engine
from backend.src.db.models import Base
from backend.src.repositories.user import UserRepository
from backend.src.api import deps

# ── 1. 日志 ──────────────────────────────────────────────
Logger.configure(LoggerConfig(
    level=LogLevel.INFO,
    app_name="smart_cs",
    json_format=False,
))
logger = get_logger()

# ── 2. 配置 ──────────────────────────────────────────────
config_path = PROJECT_ROOT / "backend" / "config" / "app.toml"
config = ConfigManager()
config.load(AppSettings, str(config_path))
settings: AppSettings = config.settings

# 手动加载嵌套配置
raw = config.raw
if "llm" in raw:
    settings.llm = LLMSettings(**raw["llm"])
if "embedding" in raw:
    settings.embedding = EmbeddingSettings(**raw["embedding"])
if "retrieval" in raw:
    settings.retrieval = RetrievalSettings(**raw["retrieval"])

# 设置 JWT 密钥
deps.set_secret_key(settings.secret_key)

# ── 3. 数据库 ────────────────────────────────────────────
init_engine(settings.database_url, echo=settings.debug)


async def init_db():
    """创建所有表 + 预置种子账号。"""
    from backend.src.db.session import engine as _engine, async_session_factory
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表创建完成")

    # 预置种子账号
    async with async_session_factory() as session:
        repo = UserRepository(session)
        if await repo.get_by_username("admin") is None:
            await repo.create_user("admin", "123456")
            logger.info("种子账号 admin 创建成功")
        await session.commit()


async def close_db():
    if engine:
        await engine.dispose()
    logger.info("数据库连接已关闭")


# ── 4. 服务器 ────────────────────────────────────────────
server = APIServer(APIConfig(
    title="智能客服填单系统",
    version="1.0.0",
    host=settings.host,
    port=settings.port,
    debug=settings.debug,
    cors_origins=settings.cors_origins,
))

server.on_startup(init_db)
server.on_shutdown(close_db)

# ── 5. 注册路由 ──────────────────────────────────────────
from backend.src.api.routes.auth import router as auth_router
from backend.src.api.routes.knowledge import router as knowledge_router
from backend.src.api.routes.ticket import router as ticket_router
from backend.src.api.routes.qc import router as qc_router
server.include_router(auth_router)
server.include_router(knowledge_router)
server.include_router(ticket_router)
server.include_router(qc_router)

# ── 6. 导出 app ──────────────────────────────────────────
app = server.app
