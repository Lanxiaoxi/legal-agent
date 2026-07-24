"""已上传文件检索工具"""
import json
import logging
from pathlib import Path
from typing import Optional

from agents import function_tool

from config import config
from session_context import current_session_id

logger = logging.getLogger(__name__)


def _get_session_dir(session_id: str) -> Path:
    return Path(config.upload_dir) / session_id


def _load_metadata(session_id: str) -> dict:
    path = _get_session_dir(session_id) / "metadata.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"files": []}


def _load_chunks(session_id: str) -> list[dict]:
    """加载 session 所有 chunk，返回 [{file_name, chunk_index, content}]"""
    chunks_dir = _get_session_dir(session_id) / "chunks"
    if not chunks_dir.exists():
        return []

    metadata = _load_metadata(session_id)
    # 建立 file_id → file_name 映射
    name_map = {f["id"]: f["name"] for f in metadata.get("files", [])}

    results = []
    for chunk_path in sorted(chunks_dir.iterdir()):
        if chunk_path.suffix != ".txt":
            continue
        # 文件名格式: {file_id}_{index}.txt
        stem = chunk_path.stem  # e.g. "abc123_001"
        parts = stem.rsplit("_", 1)
        file_id = parts[0] if len(parts) == 2 else stem
        chunk_index = parts[1] if len(parts) == 2 else "?"
        try:
            content = chunk_path.read_text(encoding="utf-8")
        except Exception:
            continue
        results.append({
            "file_name": name_map.get(file_id, file_id),
            "file_id": file_id,
            "chunk_index": chunk_index,
            "content": content,
        })
    return results


def _score_chunk(query: str, chunk_content: str) -> float:
    """基于词重叠率的简单相关度打分"""
    query_chars = set(query)
    content_chars = set(chunk_content)
    if not query_chars:
        return 0
    overlap = len(query_chars & content_chars)
    return overlap / len(query_chars)


@function_tool
def search_uploaded_file(query: str) -> str:
    """在用户已上传的文件中检索相关内容

    当用户上传了文件（合同、协议、判决书等）后，
    使用此工具按关键词或问题搜索文件中的相关段落。

    Args:
        query: 搜索关键词或问题。例如 "违约金条款"、"违约责任"、
               "劳动合同解除条件" 等。传 "list" 可列出所有已上传文件。

    Returns:
        检索到的相关文件内容，包含来源文件名和段落
    """
    session_id = current_session_id.get()
    if not session_id:
        return "错误：当前没有关联的会话"

    metadata = _load_metadata(session_id)
    files = metadata.get("files", [])

    if not files:
        return "当前会话没有上传任何文件。请先上传文件后再查询。"

    # 列出文件
    if query.strip().lower() in ("list", "列表", "文件列表"):
        lines = ["【已上传文件列表】", ""]
        for i, f in enumerate(files, 1):
            lines.append(
                f"{i}. {f['name']} "
                f"（类型: {f['type']}, 字数: {f['char_count']}, "
                f"上传时间: {f.get('created_at', '未知')[:10]}）"
            )
        return "\n".join(lines)

    # 搜索 chunks
    chunks = _load_chunks(session_id)
    if not chunks:
        return "文件内容为空或无法读取"

    # 计算相关度并排序
    scored = []
    query_lower = query.lower()
    for c in chunks:
        content_lower = c["content"].lower()
        # 精确关键词匹配加分
        exact_bonus = 2.0 if query_lower in content_lower else 0
        # 词重叠率
        overlap_score = _score_chunk(query_lower, content_lower)
        total = overlap_score + exact_bonus
        if total > 0:
            scored.append((total, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return f"在已上传文件中未找到与「{query}」相关的内容"

    # 取 top 5
    top = scored[:5]
    lines = [f"【在已上传文件中搜索「{query}」的结果】", ""]
    for rank, (score, c) in enumerate(top, 1):
        lines.append(f"--- 来源: {c['file_name']} (段落 {c['chunk_index']}) ---")
        # 截断过长内容
        content = c["content"]
        if len(content) > 800:
            content = content[:800] + "..."
        lines.append(content)
        lines.append("")

    if len(scored) > 5:
        lines.append(f"... 共找到 {len(scored)} 个相关段落，以上为最相关的 5 个")

    return "\n".join(lines)
