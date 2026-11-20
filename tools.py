"""Agent tools. Step 1: shop-docs search only."""
import chromadb
from langchain_core.tools import tool

from ingest import CHROMA_DIR, COLLECTION

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(COLLECTION)
    return _collection


@tool
def search_shop_docs(query: str) -> str:
    """Search Maple Street Auto's info docs (hours, services, price ranges, warranty, location).
    Use for any question about the shop."""
    res = _get_collection().query(query_texts=[query], n_results=4)
    chunks = [
        f"[{meta['source']}]\n{doc}"
        for doc, meta in zip(res["documents"][0], res["metadatas"][0])
    ]
    return "\n\n---\n\n".join(chunks) or "No matching information found."


TOOLS = [search_shop_docs]
