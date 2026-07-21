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


@app.get("/")
async def root():
    """健康检查端点"""
    return {"status": "ok", "message": "Legal Advisor API is running"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)