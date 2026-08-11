"""PDF 四路页面级分流提取模块

对 PDF 按页独立分流，取各引擎长处：
  A 常规页   → pdf-inspector Markdown（表格/标题/阅读顺序还原）
  B 表单页   → pdf-inspector 坐标 + 字段标签↔填写值配对
  C 编码损坏页 → PyMuPDF 单页文本（pdf-inspector 无法解码的字库更稳）
  D 扫描页   → Tesseract OCR（逐页）

路由模型：
  - 文档级决定内容类型：整份复选框+配对数量 → 表单文档 vs 规整文档
  - 页面级决定可行性：ocr_reason(scanned/garbled) → D/C，表单文档的有值页 → B

pdf-inspector 未安装或处理失败时，回退到原有 PyMuPDF + OCR 逻辑。
"""
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import fitz

logger = logging.getLogger(__name__)

try:
    import pdf_inspector
    _HAS_PDF_INSPECTOR = True
except ImportError:  # pdf-inspector 未安装时静默降级
    pdf_inspector = None
    _HAS_PDF_INSPECTOR = False

_SINGLE_DIGIT = re.compile(r"\d")


class PdfExtraction:
    """一次 PDF 提取的结果"""

    def __init__(self, text: str, route_summary: Optional[dict] = None, routed: bool = False):
        self.text = text
        self.route_summary = route_summary or {}
        self.routed = routed


# ---------- OCR ----------

_OCR_CHECKED: Optional[bool] = None


def tesseract_available() -> bool:
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


def try_ocr_page(page, page_num: int) -> str:
    """对单页 PDF 尝试 OCR，返回识别文字或空字符串"""
    if not tesseract_available():
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


# ---------- 四路页面级分流 ----------


def _is_label(it) -> bool:
    t = it.text.strip()
    if not t or it.font_size <= 0:
        return False
    return it.font_size <= 10.5 and t != "Photo"


def _is_value_candidate(it) -> bool:
    t = it.text.strip()
    if not t or it.font_size <= 0:
        return False
    if _SINGLE_DIGIT.fullmatch(t) and it.x > 520:  # 页码
        return False
    if t in ("Photo",) or t.startswith("[Image"):
        return False
    if it.y > 720 and it.x > 120:  # 页眉标题区
        return False
    return it.font_size >= 11


def _cluster_columns(xs, tol: int = 30) -> list:
    """按 x 一维聚类出"列"，返回 [(center, min, max)]"""
    xs = sorted(xs)
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [(sum(c) / len(c), min(c), max(c)) for c in clusters]


def _associate_page(page_items) -> list:
    """单页内：严格同列 + 短值 + 上方标签 的字段↔值配对"""
    labels = [i for i in page_items if _is_label(i)]
    if not labels:
        return []
    cols = _cluster_columns([l.x for l in labels])
    pairs = []
    for v in page_items:
        if not _is_value_candidate(v):
            continue
        if len(v.text.strip()) > 60:
            continue
        in_col = [c for c in cols if abs(v.x - c[0]) <= 55]
        if not in_col:
            continue
        col_center, col_min, col_max = min(in_col, key=lambda c: abs(v.x - c[0]))
        cands = [l for l in labels if l.y > v.y and col_min <= l.x <= col_max]
        if not cands:
            continue
        best = min(cands, key=lambda l: abs(l.y - v.y))
        pairs.append({"value": v.text.strip(), "label": best.text.strip(),
                      "dy": round(best.y - v.y, 1)})
    return pairs


def _doc_is_form(items) -> bool:
    """表单性 = 文档级属性：整份复选框 + 配对数量合理"""
    checkboxes = sum(i.text.count("□") for i in items)
    pairs = []
    for pg in sorted(set(i.page for i in items)):
        pairs += _associate_page([i for i in items if i.page == pg])
    return checkboxes >= 5 and 3 <= len(pairs) <= 80


def _format_pairs(pairs) -> str:
    return "\n".join(f"{p['label'].rstrip('：:')}：{p['value']}" for p in pairs)


def _route_pages(file_path: Path) -> PdfExtraction:
    """页面级四路分流主逻辑"""
    items = pdf_inspector.extract_text_with_positions(str(file_path))
    pm = pdf_inspector.extract_pages_markdown(str(file_path))
    form_doc = _doc_is_form(items)

    route_counts = {}
    parts = []
    doc = fitz.open(str(file_path))
    try:
        for pmark in pm.pages:
            p0 = pmark.page          # 0-indexed
            p1 = p0 + 1              # 1-indexed
            md = pmark.markdown or ""
            reason = pmark.ocr_reason or ""
            page_items = [i for i in items if i.page == p1]

            header = f"\n<!-- Page {p1} -->\n"
            if pmark.needs_ocr:
                if "garbled" in reason:
                    route_counts["C"] = route_counts.get("C", 0) + 1
                    out = doc[p0].get_text().strip()
                    parts.append(f"{header}{out or '[该页编码损坏，无可用文本]'}")
                else:
                    route_counts["D"] = route_counts.get("D", 0) + 1
                    ocr_text = try_ocr_page(doc[p0], p1)
                    parts.append(f"{header}{ocr_text or f'[第 {p1} 页为扫描件，OCR 不可用]'}")
            elif form_doc and len(_associate_page(page_items)) >= 3:
                route_counts["B"] = route_counts.get("B", 0) + 1
                parts.append(f"{header}{_format_pairs(_associate_page(page_items))}")
            else:
                route_counts["A"] = route_counts.get("A", 0) + 1
                parts.append(f"{header}{md}")
    finally:
        doc.close()

    text = "\n".join(parts)
    if not text.strip():
        raise RuntimeError(
            "PDF 全部页面均为扫描图片或无法提取文字，无法提取文本内容。"
            "请安装 Tesseract OCR 后重试，或使用 Adobe Acrobat / WPS 先进行文字识别。"
            "\n安装方法: apt install tesseract-ocr tesseract-ocr-chi-sim  (Linux)"
            "\n或下载: https://github.com/UB-Mannheim/tesseract/wiki (Windows)"
        )

    logger.info(f"PDF '{file_path.name}' 四路分流: {route_counts}")
    return PdfExtraction(text=text, route_summary=route_counts, routed=True)


# ---------- 回退：原有 PyMuPDF + OCR ----------


def _legacy_extract_pdf(file_path: Path) -> PdfExtraction:
    """原有逻辑：逐页 get_text + OCR 兜底"""
    doc = fitz.open(str(file_path))
    total_pages = len(doc)
    text_pages = []
    image_only_pages = []
    ocr_used = False
    try:
        for i, page in enumerate(doc, 1):
            text = page.get_text()
            if text.strip():
                text_pages.append((i, text.strip()))
            else:
                ocr_text = try_ocr_page(page, i)
                if ocr_text:
                    text_pages.append((i, ocr_text))
                    ocr_used = True
                else:
                    image_only_pages.append(i)
    finally:
        doc.close()

    if not text_pages:
        raise RuntimeError(
            f"PDF 全部 {total_pages} 页均为扫描图片，无法提取文字。"
            "请安装 Tesseract OCR 后重试，或使用 Adobe Acrobat / WPS 先进行文字识别。"
            f"\n安装方法: apt install tesseract-ocr tesseract-ocr-chi-sim  (Linux)"
            f"\n或下载: https://github.com/UB-Mannheim/tesseract/wiki (Windows)"
        )

    if image_only_pages:
        logger.info(
            f"PDF '{file_path.name}': {len(text_pages)}/{total_pages} 页有文字"
            f"（{'含 OCR ' if ocr_used else ''}），第 {image_only_pages} 页无文字已跳过"
        )
    elif ocr_used:
        logger.info(f"PDF '{file_path.name}': 全部 {total_pages} 页通过 OCR 识别完成")

    return PdfExtraction(text="\n\n".join(t for _, t in text_pages), routed=False)


def extract_pdf_text(file_path: Path, enabled: bool = True) -> PdfExtraction:
    """PDF 四路分流提取入口；pdf-inspector 不可用/失败/被禁用时回退旧逻辑"""
    if enabled and _HAS_PDF_INSPECTOR:
        try:
            return _route_pages(file_path)
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"pdf-inspector 分流失败({e})，回退 PyMuPDF+OCR")
    elif not enabled:
        logger.info("四路分流已禁用(use_pdf_routing=false)，使用 PyMuPDF+OCR 提取")
    else:
        logger.info("pdf-inspector 未安装，使用 PyMuPDF+OCR 提取")
    return _legacy_extract_pdf(file_path)
