"""PDF 解析（MVP 简版）：抽取文本层。

注意：只支持有文字层的 PDF；纯扫描件（图片型）会解析为空或乱码，
这类文件会被标记 failed——OCR 是 v2 能力（对照 RAGFlow deepdoc）。
"""
from pathlib import Path

from pypdf import PdfReader


def parse(path: Path) -> str:
    """逐页抽取 PDF 文本层。"""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"【第{i}页】\n{text}")
    return "\n\n".join(pages)
