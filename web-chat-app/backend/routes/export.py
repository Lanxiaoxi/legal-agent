"""导出路由模块 - markdown 转 Word 文档"""
import asyncio
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 临时导出目录
EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# 生成 Word 文档的 MIME 类型
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# pandoc 可执行文件路径（模块级缓存）
_pandoc_path: Optional[str] = None


def _find_pandoc() -> Optional[str]:
    """查找 pandoc 可执行文件路径"""
    global _pandoc_path
    if _pandoc_path is not None:
        return _pandoc_path

    candidates = [
        "pandoc",
        # Windows 常见路径
        r"C:\Program Files\Pandoc\pandoc.exe",
        r"C:\Program Files (x86)\Pandoc\pandoc.exe",
        # macOS / Linux 常见路径
        "/usr/bin/pandoc",
        "/usr/local/bin/pandoc",
        "/opt/homebrew/bin/pandoc",
    ]
    for candidate in candidates:
        if shutil.which(candidate) or Path(candidate).exists():
            _pandoc_path = candidate
            logger.info(f"Pandoc found at: {candidate}")
            return candidate
    return None


def _derive_filename(markdown: str) -> str:
    """从 markdown 内容提取文件名（取第一行标题），无标题则用默认名"""
    for line in markdown.strip().splitlines():
        line = line.strip()
        # 匹配 "# 标题" 或 "标题" 形式
        if line.startswith("#"):
            name = line.lstrip("#").strip()
            if name:
                return name
    return "文档"


class ExportRequest(BaseModel):
    markdown: str
    filename: Optional[str] = None


@router.post("/api/export")
async def export_docx(req: ExportRequest):
    """将 markdown 内容转换为 Word 文档 (.docx)

    Args:
        req: 包含 markdown 内容，可选的文件名

    Returns:
        .docx 文件下载响应
    """
    if not req.markdown.strip():
        raise HTTPException(status_code=400, detail="markdown 内容为空，无法导出")

    pandoc = _find_pandoc()
    if not pandoc:
        raise HTTPException(
            status_code=500,
            detail="服务器未安装 pandoc，无法导出 Word 文档。请安装后重试: sudo apt install -y pandoc"
        )

    # 生成唯一文件名，避免并发冲突
    token = uuid.uuid4().hex[:8]
    md_path = EXPORT_DIR / f"_{token}.md"
    docx_path = EXPORT_DIR / f"_{token}.docx"

    try:
        md_path.write_text(req.markdown, encoding="utf-8")

        result = subprocess.run(
            [pandoc, str(md_path), "-o", str(docx_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown error"
            logger.error(f"Pandoc conversion failed: {stderr}")
            raise HTTPException(status_code=500, detail=f"文档转换失败: {stderr}")

        if not docx_path.exists() or docx_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="文档转换失败：未生成有效文件")

        # 导出文件名：优先用请求中的文件名，否则从内容提取
        base_name = (req.filename or _derive_filename(req.markdown)).strip()
        # 去掉非法文件名字符
        for ch in '\\/:*?"<>|':
            base_name = base_name.replace(ch, "_")
        download_name = f"{base_name}.docx"

        logger.info(f"[EXPORT] markdown={len(req.markdown)} chars → {download_name}")
        return FileResponse(
            path=str(docx_path),
            media_type=DOCX_MIME,
            filename=download_name,
        )

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="文档转换超时，请稍后重试")
    except Exception as e:
        logger.error(f"[EXPORT] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
    finally:
        # 清理临时文件（FileResponse 读取在响应后完成，延迟删除）
        async def _cleanup():
            await asyncio.sleep(30)
            md_path.unlink(missing_ok=True)
            docx_path.unlink(missing_ok=True)

        asyncio.create_task(_cleanup())
