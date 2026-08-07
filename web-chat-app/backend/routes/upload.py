"""文件上传路由模块"""
import json
import logging
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import docx
import fitz  # pymupdf
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import config

logger = logging.getLogger(__name__)

router = APIRouter()

# 支持的文件类型
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".bmp"}
# 单次会话最大总文件大小
MAX_SESSION_SIZE_MB = 50

# ---------- LibreOffice 路径检测 ----------

_LO_PATH: Optional[str] = None


def _find_libreoffice() -> Optional[str]:
    """查找 LibreOffice 可执行文件路径"""
    global _LO_PATH
    if _LO_PATH is not None:
        return _LO_PATH

    candidates = [
        "libreoffice",
        "soffice",
        # Windows 常见路径
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        # macOS
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for candidate in candidates:
        if shutil.which(candidate) or Path(candidate).exists():
            _LO_PATH = candidate
            logger.info(f"LibreOffice found at: {candidate}")
            return candidate
    return None


# ---------- 文本提取 ----------


def _extract_doc_text(file_path: Path) -> str:
    """从 .doc 文件中提取文本（通过 LibreOffice 转换）"""
    lo = _find_libreoffice()
    if not lo:
        raise RuntimeError(
            "需要 LibreOffice 来解析 .doc 文件（旧版 Word 格式）。"
            "请安装 LibreOffice: https://www.libreoffice.org/download/"
        )

    out_dir = file_path.parent
    result = subprocess.run(
        [lo, "--headless", "--convert-to", "txt:Text",
         "--outdir", str(out_dir), str(file_path)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"LibreOffice 转换失败: {stderr}")

    # LibreOffice 输出文件名: 原文件名.txt
    txt_path = file_path.with_suffix(".txt")
    if not txt_path.exists():
        raise RuntimeError("LibreOffice 转换后未生成文本文件")

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    txt_path.unlink(missing_ok=True)  # 清理临时 txt
    return text


# ---------- OCR ----------

_OCR_CHECKED: Optional[bool] = None


def _tesseract_available() -> bool:
    """检测 Tesseract OCR 是否可用"""
    global _OCR_CHECKED
    if _OCR_CHECKED is not None:
        return _OCR_CHECKED
    _OCR_CHECKED = shutil.which("tesseract") is not None
    if _OCR_CHECKED:
        logger.info("Tesseract OCR detected")
    else:
        logger.info("Tesseract not found — PDF scanned pages will be skipped")
    return _OCR_CHECKED


def _try_ocr_page(page, page_num: int) -> str:
    """对单页 PDF 尝试 OCR，返回识别文字或空字符串"""
    if not _tesseract_available():
        return ""

    try:
        # 中文为主 + 英文为辅；dpi=300 平衡速度和精度
        tp = page.get_textpage_ocr(flags=3, language="chi_sim+eng", dpi=300)
        text = page.get_text(textpage=tp)
        if text.strip():
            logger.info(f"OCR: page {page_num} → {len(text)} chars")
            return text
    except Exception as e:
        logger.warning(f"OCR failed on page {page_num}: {e}")

    return ""


def _extract_image_text(file_path: Path) -> str:
    """从图片中提取文字（通过 OCR）"""
    doc = fitz.open(str(file_path))  # 图片按单页文档打开
    try:
        page = doc[0]
        # 图片没有文字层，直接 OCR
        text = _try_ocr_page(page, 1)
        if not text:
            raise RuntimeError(
                f"无法从图片中识别出文字。"
                "请确认图片包含清晰的文字内容，或已安装 Tesseract OCR。"
            )
        return text
    finally:
        doc.close()


def _extract_text(file_path: Path, ext: str) -> str:
    """从文件中提取纯文本"""
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
        return text

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
        return "\n".join(paragraphs)

    if ext == ".doc":
        return _extract_doc_text(file_path)

    if ext in {".jpg", ".jpeg", ".png", ".bmp"}:
        return _extract_image_text(file_path)

    if ext == ".pdf":
        doc = fitz.open(str(file_path))
        total_pages = len(doc)
        text_pages = []
        image_only_pages = []
        ocr_used = False

        for i, page in enumerate(doc, 1):
            text = page.get_text()
            if text.strip():
                text_pages.append((i, text.strip()))
            else:
                # 无文字层，尝试 OCR 兜底
                ocr_text = _try_ocr_page(page, i)
                if ocr_text:
                    text_pages.append((i, ocr_text))
                    ocr_used = True
                else:
                    image_only_pages.append(i)
        doc.close()

        if not text_pages:
            # 全部为图片页且 OCR 不可用/失败
            raise RuntimeError(
                f"PDF 全部 {total_pages} 页均为扫描图片，无法提取文字。"
                "请安装 Tesseract OCR 后重试，或使用 Adobe Acrobat / WPS 先进行文字识别。"
                f"\n安装方法: apt install tesseract-ocr tesseract-ocr-chi-sim  (Linux)"
                f"\n或下载: https://github.com/UB-Mannheim/tesseract/wiki (Windows)"
            )

        if image_only_pages:
            logger.info(
                f"PDF '{file_path.name}': {len(text_pages)}/{total_pages} 页有文字"
                f"（{'含 OCR ' if ocr_used else ''}），"
                f"第 {image_only_pages} 页无文字已跳过"
            )
        elif ocr_used:
            logger.info(
                f"PDF '{file_path.name}': 全部 {total_pages} 页通过 OCR 识别完成"
            )

        return "\n\n".join(text for _, text in text_pages)

    return ""


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
        text = _extract_text(tmp_path, ext)
        if not text.strip():
            file_bytes = tmp_path.read_bytes() if tmp_path.exists() else content
            detail = (
                f"无法从文件中提取文本内容。"
                f"文件类型: {ext}，大小: {file_size} 字节。"
                f"{'TXT 文件可能是空文件或编码不受支持。' if ext == '.txt' else ''}"
                f"{'DOCX/DOC 文件可能只包含图片或格式不受支持。' if ext in ('.docx', '.doc') else ''}"
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
