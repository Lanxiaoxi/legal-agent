"""文档转换公共模块 - markdown 转 Word (.docx)"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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


def pandoc_available() -> bool:
    """检查 pandoc 是否可用"""
    return _find_pandoc() is not None


def markdown_to_docx(markdown: str, output_path: Path, timeout: int = 60) -> None:
    """将 markdown 内容转换为 .docx 文件

    Args:
        markdown: markdown 内容
        output_path: 输出 .docx 文件路径
        timeout: pandoc 转换超时（秒）

    Raises:
        RuntimeError: pandoc 未安装或转换失败
    """
    pandoc = _find_pandoc()
    if not pandoc:
        raise RuntimeError(
            "服务器未安装 pandoc，无法生成 Word 文档。"
            "请安装: sudo apt install -y pandoc"
        )

    # 临时 markdown 文件
    md_path = output_path.with_suffix(".md")
    md_path.write_text(markdown, encoding="utf-8")

    try:
        result = subprocess.run(
            [pandoc, str(md_path), "-o", str(output_path)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            logger.error(f"Pandoc conversion failed: {stderr}")
            raise RuntimeError(f"文档转换失败: {stderr}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("文档转换失败：未生成有效文件")
    except subprocess.TimeoutExpired:
        raise RuntimeError("文档转换超时，请稍后重试")
    finally:
        md_path.unlink(missing_ok=True)
