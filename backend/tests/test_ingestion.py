"""切分逻辑单元测试。"""
from app.services.ingestion import chunk_text, estimate_tokens


def test_chunk_respects_sentence_boundaries() -> None:
    """除最后一块外，切片结尾必须是句边界（文档结尾允许无标点）。"""
    text = "第一句话。第二句话！第三句话？第四句话；第五句话\n"
    chunks = chunk_text(text, budget=6)  # 小预算强制多块
    assert len(chunks) >= 2
    for chunk in chunks[:-1]:
        assert chunk[-1] in "。！？；\n"


def test_chunk_packs_within_budget() -> None:
    """每块不超过 token 预算（允许最后一块）。"""
    text = "这是一个句子。" * 50
    budget = 40
    for chunk in chunk_text(text, budget=budget):
        assert estimate_tokens(chunk) <= budget * 1.2  # 估算误差容忍 20%


def test_chunk_empty_and_short() -> None:
    """空文本返回空列表；短文本返回单块。"""
    assert chunk_text("") == []
    assert chunk_text("就一句。") == ["就一句。"]
