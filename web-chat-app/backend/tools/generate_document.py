"""文档生成工具 - 将 AI 起草的 markdown 内容转为 Word 文档"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agents import function_tool

from config import config
from services.doc_converter import markdown_to_docx, pandoc_available
from session_context import current_session_id

logger = logging.getLogger(__name__)


def _get_session_dir(session_id: str) -> Path:
    return Path(config.upload_dir) / session_id


def _load_metadata(session_id: str) -> dict:
    path = _get_session_dir(session_id) / "metadata.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"files": []}


def _save_metadata(session_id: str, metadata: dict):
    path = _get_session_dir(session_id) / "metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


@function_tool
def generate_document(content: str, filename: str) -> str:
    """将 AI 起草的文档内容转换为 Word 文档供用户下载

    当用户需要起草正式法律文书（合同、协议、起诉状、承诺书、
    法律意见书、律师函等）时，先在对话中完成内容起草并确认，
    然后调用此工具生成可下载的 .docx 文件。

    Args:
        content: 完整的文档内容（markdown 格式，使用 # 标题、## 分节、- 列表）
        filename: 文档标题名，如 "软件开发保密协议"。不要带扩展名。

    Returns:
        生成结果，包含文件名，或错误提示
    """
    session_id = current_session_id.get()
    if not session_id:
        return "错误：当前没有关联的会话，无法生成文档"

    # 清理文件名中的非法字符
    filename = filename.strip() or "文档"
    for ch in '\\/:*?"<>|':
        filename = filename.replace(ch, "_")

    if not content.strip():
        return "错误：文档内容为空，无法生成"

    if not pandoc_available():
        return (
            "错误：服务器未安装 pandoc，无法生成 Word 文档。"
            "请管理员执行: sudo apt install -y pandoc"
        )

    try:
        file_id = str(uuid.uuid4())[:8]
        files_dir = _get_session_dir(session_id) / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        output_path = files_dir / f"{file_id}.docx"

        # 转换 markdown → docx
        markdown_to_docx(content, output_path)

        # 更新元数据
        metadata = _load_metadata(session_id)
        file_info = {
            "id": file_id,
            "name": f"{filename}.docx",
            "type": "docx",
            "size": output_path.stat().st_size,
            "char_count": len(content),
            "chunk_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generated": True,  # 标记为 AI 生成的文档，前端可点击下载
        }
        metadata["files"].append(file_info)
        metadata["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
        _save_metadata(session_id, metadata)

        logger.info(
            f"[GEN_DOC] session={session_id} file={filename}.docx "
            f"chars={len(content)} file_id={file_id}"
        )
        return f"文档已生成: {filename}.docx"
    except Exception as e:
        logger.error(f"[GEN_DOC] Failed to generate document: {e}")
        return f"文档生成失败: {e}"
