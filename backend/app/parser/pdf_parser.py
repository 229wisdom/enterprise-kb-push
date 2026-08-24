"""PDF 解析：文本层优先，扫描件页面自动走 OCR（对照 RAGFlow deepdoc 的思路）。

流程：PyMuPDF 逐页抽文本 → 无文本的页 = 扫描图 → 渲染成图片 → RapidOCR 识别。
全部本地离线完成（onnxruntime），不外发数据。
"""
from pathlib import Path

import fitz  # PyMuPDF

_ocr_engine = None  # 懒加载：只在真遇到扫描页时才初始化（加载模型要几秒）


def _get_ocr():
    """懒加载 RapidOCR 引擎（单例）。"""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def parse(path: Path) -> str:
    """解析 PDF：有文本层直接抽，扫描页走 OCR。"""
    doc = fitz.open(str(path))
    pages: list[str] = []
    ocr_pages = 0
    try:
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text().strip()
            if not text:  # 扫描页：渲染成图 → OCR
                pix = page.get_pixmap(dpi=200)
                result, _ = _get_ocr()(pix.tobytes("png"))
                text = "\n".join(line[1] for line in (result or [])).strip()
                if text:
                    ocr_pages += 1
            if text:
                pages.append(f"【第{i+1}页】\n{text}")
    finally:
        doc.close()
    if ocr_pages:
        pages.insert(0, f"（本文档含 {ocr_pages} 页扫描件，已 OCR 识别）")
    return "\n\n".join(pages)
