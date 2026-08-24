"""向量库接口（Chroma 实现）。

业务层只依赖本模块的函数，不直接接触 chromadb——
以后换 Qdrant/ES 时只改本文件，业务代码不动（架构文档 §6.2）。
"""
import chromadb

from app.core.config import settings

_client = chromadb.PersistentClient(path=str(settings.data_dir / "chroma"))
_collection = _client.get_or_create_collection(
    name="chunks",
    metadata={"hnsw:space": "cosine"},  # 余弦相似度
)


def add_chunks(ids: list[str], embeddings: list[list[float]], metadatas: list[dict]) -> None:
    """把切片向量连同权限元数据（doc_id/dept_ids/clearance）存入向量库。"""
    _collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)


def search(query_embedding: list[float], dept_ids: list[int], max_clearance: int, top_k: int) -> list[dict]:
    """在【权限范围内】检索最相似的切片。

    权限过滤就发生在这里（红线①）：
    - 普通员工：只查本部门且密级≤自身密级的切片
    - 老板：调用方传入全部部门 id 与密级 3，等于不过滤
    返回: [{"chroma_id","doc_id","content_meta","distance"}...]，按相似度从高到低
    """
    where = {
        "$and": [
            {"dept_id": {"$in": dept_ids}},
            {"clearance": {"$lte": max_clearance}},
        ]
    }
    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )
    hits = []
    for i, chroma_id in enumerate(result["ids"][0]):
        hits.append({
            "chroma_id": chroma_id,
            "doc_id": result["metadatas"][0][i]["doc_id"],
            "distance": result["distances"][0][i],
        })
    return hits


def delete_by_doc(doc_id: int) -> None:
    """删除某文档的全部向量（文档删除时调用）。"""
    _collection.delete(where={"doc_id": doc_id})


def count() -> int:
    """向量总数（健康检查/调试用）。"""
    return _collection.count()
