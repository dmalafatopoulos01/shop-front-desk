"""Load docs/*.md into a local Chroma collection (default local embeddings, no key)."""
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

# Hosting: keep the embedding model inside the project so a build-time download survives
# sleep/wake (the home directory cache may not). Unset locally, Chroma's default is used.
if os.environ.get("CHROMA_MODEL_DIR"):
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = Path(os.environ["CHROMA_MODEL_DIR"]).resolve() / "all-MiniLM-L6-v2"

ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "docs"
CHROMA_DIR = ROOT / ".chroma"
COLLECTION = "shop_docs"


def chunk_text(text: str) -> list[str]:
    """Split on blank lines; keep each doc's title line attached to its chunks."""
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    title = parts[0] if parts and parts[0].startswith("#") else ""
    body = parts[1:] if title else parts
    return [f"{title}\n\n{p}" if title else p for p in body]


def ingest() -> int:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION)  # rebuild: idempotent
    except Exception:
        pass
    col = client.create_collection(COLLECTION)

    ids, docs, metas = [], [], []
    for path in sorted(DOCS_DIR.glob("*.md")):
        for i, chunk in enumerate(chunk_text(path.read_text(encoding="utf-8"))):
            ids.append(f"{path.stem}-{i}")
            docs.append(chunk)
            metas.append({"source": path.name})
    col.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


if __name__ == "__main__":
    print(f"Ingested {ingest()} chunks into {CHROMA_DIR}")
