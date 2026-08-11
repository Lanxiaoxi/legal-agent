"""文件上传路由模块"""
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import docx
import fitz  # pymupdf
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import config
from services.pdf_routing import extract_pdf_text, try_ocr_page

logger = logging.getLogger(__name__)

router = APIRouter()

# 支持的文件类型
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".bmp"}
# 单次会话最大总文件大小
MAX_SESSION_SIZE_MB = 50

# ---------- 文本提取 ----------


def _extract_image_text(file_path: Path) -> str:
    """从图片中提取文字（通过 OCR）"""
    doc = fitz.open(str(file_path))  # 图片按单页文档打开
    try:
        page = doc[0]
        # 图片没有文字层，直接 OCR
        text = try_ocr_page(page, 1)
        if not text:
            raise RuntimeError(
                f"无法从图片中识别出文字。"
                "请确认图片包含清晰的文字内容，或已安装 Tesseract OCR。"
            )
        return text
    finally:
        doc.close()


def _extract_text(file_path: Path, ext: str) -> tuple[str, dict]:
    """从文件中提取纯文本，返回 (text, extra)

    extra: PDF 时包含 route_summary / routed 信息，其余类型为空 dict
    """
    if ext == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            # 尝试以其他编码读取
            for enc in ["gbk", "gb2312", "latin-1"]:
                try:
                    text = file_path.read_text(encoding=enc)
                    if text.strip():
                        logger.info(f"File {file_path.name} decoded with {enc}")
                        break
                except (UnicodeDecodeError, LookupError):
                    continue
        return text, {}

    if ext == ".docx":
        doc = docx.Document(str(file_path))
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        # 也提取表格内容
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text = cell.text.strip()
                    if text:
                        paragraphs.append(text)
        return "\n".join(paragraphs), {}

    if ext in {".jpg", ".jpeg", ".png", ".bmp"}:
        return _extract_image_text(file_path), {}

    if ext == ".pdf":
        # 四路页面级分流（pdf-inspector），失败/禁用时自动回退 PyMuPDF + OCR
        result = extract_pdf_text(file_path, config.use_pdf_routing)
        return result.text, {"route_summary": result.route_summary, "routed": result.routed}

    return "", {}


# ---------- 分块 ----------


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 100) -> list[str]:
    """将文本按自然段落分块，每块不超过 chunk_size 字"""
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            # 如果单个段落超过 chunk_size，硬切
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


# ---------- 存储管理 ----------


def _get_session_dir(session_id: str) -> Path:
    return Path(config.upload_dir) / session_id


def _get_metadata_path(session_id: str) -> Path:
    return _get_session_dir(session_id) / "metadata.json"


def _get_chunks_dir(session_id: str) -> Path:
    return _get_session_dir(session_id) / "chunks"


def _load_metadata(session_id: str) -> dict:
    path = _get_metadata_path(session_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"files": [], "last_accessed_at": datetime.now(timezone.utc).isoformat()}


def _save_metadata(session_id: str, metadata: dict):
    path = _get_metadata_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch_access(session_id: str):
    """更新 last_accessed_at"""
    metadata = _load_metadata(session_id)
    metadata["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
    _save_metadata(session_id, metadata)


def _get_session_total_size(session_id: str) -> int:
    """获取 session 总存储大小（字节）"""
    session_dir = _get_session_dir(session_id)
    if not session_dir.exists():
        return 0
    total = 0
    for f in session_dir.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


# ---------- API 端点 ----------


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
    user_id: str = Form(default=""),
):
    """上传文件并提取文本分块存储

    Args:
        file: 上传的文件
        session_id: 会话 ID
        user_id: 匿名用户 ID

    Returns:
        {files: [{file_id, name, type, size, chunk_count, created_at}]}
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    # 验证文件扩展名
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    # .doc 旧版格式不再支持，引导用户转换
    if ext == ".doc":
        raise HTTPException(
            status_code=400,
            detail="暂不支持 .doc 格式，请先用 Word / WPS 将文档另存为 .docx 后再上传。"
        )

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{ext}'，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 验证大小
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    max_bytes = config.upload_max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小 {file_size / 1024 / 1024:.1f}MB 超过限制 {config.upload_max_size_mb}MB"
        )

    # 检查 session 总文件大小
    current_total = _get_session_total_size(session_id)
    if current_total + file_size > MAX_SESSION_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"会话文件总大小超过 {MAX_SESSION_SIZE_MB}MB 限制"
        )

    # 生成 file_id 并存储
    file_id = str(uuid.uuid4())[:8]
    session_dir = _get_session_dir(session_id)
    chunks_dir = _get_chunks_dir(session_id)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # 保存原始文件到临时路径用于提取
    tmp_path = session_dir / f"_tmp_{file_id}{ext}"
    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        # 提取文本
        text, extract_extra = _extract_text(tmp_path, ext)
        if not text.strip():
            file_bytes = tmp_path.read_bytes() if tmp_path.exists() else content
            detail = (
                f"无法从文件中提取文本内容。"
                f"文件类型: {ext}，大小: {file_size} 字节。"
                f"{'TXT 文件可能是空文件或编码不受支持。' if ext == '.txt' else ''}"
                f"{'DOCX 文件可能只包含图片或格式不受支持。' if ext == '.docx' else ''}"
            )
            raise HTTPException(status_code=400, detail=detail)
    except RuntimeError as e:
        # _extract_text 主动抛出的错误（如 PDF 扫描件），直接作为 400 返回
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # 删除临时文件
        tmp_path.unlink(missing_ok=True)

    # 分块并存储
    chunks = _chunk_text(text)
    for i, chunk in enumerate(chunks, 1):
        chunk_path = chunks_dir / f"{file_id}_{i:03d}.txt"
        chunk_path.write_text(chunk, encoding="utf-8")

    # 更新元数据
    metadata = _load_metadata(session_id)
    file_info = {
        "id": file_id,
        "name": filename,
        "type": ext.lstrip("."),
        "size": file_size,
        "char_count": len(text),
        "chunk_count": len(chunks),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "extract_mode": "pdf_routed" if extract_extra.get("routed") else "legacy",
        "route_summary": extract_extra.get("route_summary"),
    }
    metadata["files"].append(file_info)
    metadata["user_id"] = user_id or None
    metadata["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
    _save_metadata(session_id, metadata)

    logger.info(
        f"[UPLOAD] session={session_id} user={user_id} file={filename} "
        f"size={file_size}B chunks={len(chunks)} file_id={file_id}"
    )

    return {"files": metadata["files"]}


@router.get("/api/files/{session_id}")
async def list_files(session_id: str):
    """列出某 session 的上传文件

    Args:
        session_id: 会话 ID

    Returns:
        {files: [...]}
    """
    _touch_access(session_id)
    metadata = _load_metadata(session_id)
    if not metadata.get("files"):
        return {"files": []}
    return {"files": metadata["files"]}


@router.get("/api/files/{session_id}/{file_id}")
async def download_file(session_id: str, file_id: str):
    """下载某 session 的指定文件（目前仅支持 AI 生成的 .docx 文档）

    Args:
        session_id: 会话 ID
        file_id: 文件 ID

    Returns:
        文件下载响应
    """
    # 查找 AI 生成的文档
    files_dir = _get_session_dir(session_id) / "files"
    docx_path = files_dir / f"{file_id}.docx"
    if not docx_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    metadata = _load_metadata(session_id)
    file_info = next((f for f in metadata.get("files", []) if f.get("id") == file_id), None)
    download_name = file_info.get("name", f"{file_id}.docx") if file_info else f"{file_id}.docx"

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )


@router.delete("/api/files/{session_id}")
async def delete_files(session_id: str):
    """清理某 session 的所有上传文件

    Args:
        session_id: 会话 ID
    """
    session_dir = _get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)
        logger.info(f"[CLEANUP] Deleted files for session={session_id}")
    return {"status": "ok", "message": "Files cleaned up"}


# ---------- TTL 清理 ----------


async def cleanup_expired_files():
    """清理超过 TTL 的 session 目录（后台任务，由 main.py 启动）"""
    import asyncio

    while True:
        await asyncio.sleep(3600)  # 每小时检查一次
        upload_dir = Path(config.upload_dir)
        if not upload_dir.exists():
            continue

        ttl_seconds = config.upload_ttl_days * 24 * 3600
        now = datetime.now(timezone.utc)

        for session_dir in upload_dir.iterdir():
            if not session_dir.is_dir():
                continue
            metadata_path = session_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                last_accessed = datetime.fromisoformat(
                    metadata.get("last_accessed_at", "2000-01-01T00:00:00+00:00")
                )
                if (now - last_accessed).total_seconds() > ttl_seconds:
                    shutil.rmtree(session_dir)
                    logger.info(
                        f"[TTL] Cleaned up expired session={session_dir.name}, "
                        f"last_accessed={last_accessed.isoformat()}"
                    )
            except Exception as e:
                logger.warning(f"[TTL] Error processing {session_dir}: {e}")
