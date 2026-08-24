"""解析器调度：按文件后缀分发到对应解析器。

新增格式 = 新增一个解析文件 + 在 PARSERS 注册一行（开闭原则）。
"""
from pathlib import Path

from app.parser import docx_parser, pdf_parser, txt_parser, xlsx_parser


class UnsupportedFormatError(Exception):
    """不支持的文件格式。"""


PARSERS = {
    ".txt": txt_parser.parse,
    ".md": txt_parser.parse,
    ".xlsx": xlsx_parser.parse,
    ".pdf": pdf_parser.parse,
    ".docx": docx_parser.parse,
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB（业务规则）


def parse_file(path: Path) -> str:
    """把文件解析成纯文本。失败抛异常（由上层标记 failed）。"""
    if path.stat().st_size > MAX_FILE_SIZE:
        raise UnsupportedFormatError(f"文件超过 50MB 限制: {path.name}")
    suffix = path.suffix.lower()
    parser = PARSERS.get(suffix)
    if parser is None:
        raise UnsupportedFormatError(f"不支持的格式 {suffix}（支持: {', '.join(PARSERS)}）")
    text = parser(path)
    if not text.strip():
        raise ValueError(f"解析结果为空: {path.name}")
    return text
