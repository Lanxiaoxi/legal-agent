"""Legal Advisor API - 主应用入口"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config
from routes.chat import router as chat_router

# 禁用 tracing 以避免需要 OpenAI API key
from agents import set_tracing_disabled
set_tracing_disabled(disabled=True)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="Legal Advisor API")

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.cors_origin],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

# 注册路由
app.include_router(chat_router)

from routes.upload import router as upload_router
app.include_router(upload_router)


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