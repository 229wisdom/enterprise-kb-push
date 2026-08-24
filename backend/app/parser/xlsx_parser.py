"""Excel 解析：每个 sheet 转成"行=文本"的格式，表头拼进每行保证语义完整。"""
from pathlib import Path

import openpyxl


def parse(path: Path) -> str:
    """把 xlsx 转成文本行：'列名1: 值1, 列名2: 值2' 每行一条记录。"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines: list[str] = []
    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(h) if h is not None else "" for h in rows[0]]
        lines.append(f"【表: {sheet.title}】")
        for row in rows[1:]:
            cells = [f"{headers[i]}: {v}" for i, v in enumerate(row) if v is not None and i < len(headers)]
            if cells:
                lines.append(", ".join(cells))
    wb.close()
    return "\n".join(lines)
