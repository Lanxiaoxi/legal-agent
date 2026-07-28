"""用户反馈路由模块"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# 反馈存储目录
FEEDBACK_DIR = Path(__file__).parent.parent / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


class FeedbackRequest(BaseModel):
    """反馈请求体"""
    content: str = Field(..., min_length=1, max_length=5000, description="反馈内容")
    user_id: Optional[str] = Field(default=None, max_length=100, description="匿名用户 ID")


@router.post("/api/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """提交用户反馈，保存为 JSON 文件到 backend/feedback/ 目录"""

    feedback_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc)

    entry = {
        "id": feedback_id,
        "content": feedback.content.strip(),
        "user_id": feedback.user_id,
        "created_at": created_at.isoformat(),
    }

    file_path = FEEDBACK_DIR / f"{feedback_id}.json"
    file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[FEEDBACK] id={feedback_id} user={feedback.user_id} content_len={len(feedback.content)}")

    return {"status": "ok", "id": feedback_id, "message": "感谢您的反馈！"}
