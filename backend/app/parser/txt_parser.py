"""TXT/Markdown 解析：直接读文本。"""
from pathlib import Path


def parse(path: Path) -> str:
    """读取纯文本文件（自动尝试 utf-8/gbk 编码）。"""
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {path.name}")
