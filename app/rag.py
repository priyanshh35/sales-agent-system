import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.llm import get_embedding, rerank_texts

chroma_client = chromadb.PersistentClient(
    path=settings.CHROMA_DB_PATH,
    settings=ChromaSettings(anonymized_telemetry=False)
)


def get_collection(name: str):
    """Get or create a named ChromaDB collection."""
    return chroma_client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )


def add_documents(collection_name: str, documents: list[dict]):
    """
    Add documents to a named collection.
    Each doc: {"id": str, "text": str, "metadata": dict}
    """
    collection = get_collection(collection_name)
    collection.add(
        ids=[d["id"] for d in documents],
        documents=[d["text"] for d in documents],
        embeddings=[get_embedding(d["text"]) for d in documents],
        metadatas=[d.get("metadata", {}) for d in documents]
    )


def retrieve(
    collection_name: str,
    query: str,
    n_results: int = 5,
    where: dict = None
) -> list[dict]:
    """Vector similarity search in a named collection."""
    collection = get_collection(collection_name)
    if collection.count() == 0:
        return []

    query_embedding = get_embedding(query)
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(n_results, collection.count()),
        "include": ["documents", "metadatas", "distances"]
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        output.append({"text": doc, "metadata": meta, "distance": dist})
    return output


def retrieve_and_rerank(
    collection_name: str,
    query: str,
    n_results: int = 5,
    top_k: int = 3,
    where: dict = None
) -> list[dict]:
    """Full pipeline: embed → retrieve → rerank → top_k."""
    chunks = retrieve(collection_name, query, n_results, where)
    if not chunks:
        return []

    texts = [c["text"] for c in chunks]
    try:
        reranked = rerank_texts(query, texts)
        result = []
        for r in reranked:
            chunk = chunks[r["index"]].copy()
            chunk["rerank_score"] = r["score"]
            result.append(chunk)
        return result[:top_k]
    except Exception as e:
        print(f"[RAG] Reranker failed: {e}")
        return sorted(chunks, key=lambda x: x["distance"])[:top_k]