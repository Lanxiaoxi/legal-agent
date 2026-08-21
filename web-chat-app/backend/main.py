"""Legal Advisor API - 主应用入口"""
import os
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config
from routes.chat import router as chat_router

# 禁用 tracing 以避免需要 OpenAI API key
from agents import set_tracing_disabled
set_tracing_disabled(disabled=True)

# 配置日志（路径可用环境变量 LOG_FILE 覆盖，默认 backend/logs/backend.log）
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(os.getenv("LOG_FILE", str(LOG_DIR / "backend.log")))

# 日志格式
LOG_FORMAT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def _make_file_handler(path: Path):
    """创建文件 handler；文件被外部进程锁定（如句柄残留）时自动换时间戳文件名"""
    handler = None
    for candidate in (path, LOG_DIR / f"backend_{datetime.now():%H%M%S}.log"):
        try:
            handler = TimedRotatingFileHandler(
                str(candidate), when="midnight", interval=1, backupCount=30, encoding="utf-8"
            )
            if candidate != path:
                logging.getLogger(__name__).warning(
                    f"日志文件 {path.name} 被占用，改用 {candidate.name}"
                )
            break
        except OSError:
            continue
    if handler is None:
        handler = logging.StreamHandler()  # 兜底：只输出到控制台
    handler.setLevel(logging.INFO)
    handler.setFormatter(LOG_FORMAT)
    return handler


# 文件 handler — 每天轮转，保留 30 天
file_handler = _make_file_handler(LOG_FILE)

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(LOG_FORMAT)

# 根 logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Legal Advisor API")

# 配置 CORS 中间件（支持 "*" 通配或逗号分隔多源，本地/云部署共用）
cors_origins = (
    ["*"]
    if config.cors_origin == "*"
    else [o.strip() for o in config.cors_origin.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"]
)

# 注册路由
app.include_router(chat_router)

from routes.upload import router as upload_router
app.include_router(upload_router)

from routes.feedback import router as feedback_router
app.include_router(feedback_router)


@app.get("/")
async def root():
    """健康检查端点"""
    logger.info("Health check endpoint called")
    return {"status": "ok", "message": "Legal Advisor API is running"}


@app.on_event("startup")
async def startup_event():
    """启动时创建上传目录并启动 TTL 清理任务"""
    import asyncio
    from pathlib import Path

    upload_dir = Path(config.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    from routes.upload import cleanup_expired_files
    asyncio.create_task(cleanup_expired_files())
    logger.info(f"Upload dir: {upload_dir.absolute()}, TTL: {config.upload_ttl_days} days")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Legal Advisor API on port {port}")
    logger.info(f"CORS enabled for: {config.cors_origin}")
    logger.info(f"Default model: {config.model}")
    uvicorn.run(app, host="0.0.0.0", port=port)