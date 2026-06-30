import json
import base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from src.config import (
    DOCUMENT_STORE_PATH,
    EXTRACTED_IMAGES_DIR,
    CHROMA_DB_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    PDF_REGISTRY_PATH,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    VLM_MODEL_NAME,
    VLM_SUMMARY_PROMPT,
)

VLM_CONCURRENCY = 5
VLM_SAVE_INTERVAL = 10

ProgressCallback = Optional[Callable[[int, int, str], None]]


def build_index(progress_callback: ProgressCallback = None) -> None:
    """Full indexing pipeline: VLM summaries → embeddings → ChromaDB.

    Reads document_store.json (created by extract.py), generates VLM
    descriptions for images, embeds everything, and indexes in ChromaDB.
    Wipes and recreates the ChromaDB collection.
    """
    if not DOCUMENT_STORE_PATH.exists():
        raise FileNotFoundError(
            "document_store.json not found. Run extract.py first."
        )

    store: dict = json.loads(DOCUMENT_STORE_PATH.read_text())

    # Phase 1: Generate VLM summaries for all images with content=None
    _generate_vlm_summaries(store, progress_callback)

    # Phase 2: Embed and index in ChromaDB (full rebuild)
    if progress_callback:
        progress_callback(0, 1, "Embedding and indexing in ChromaDB...")
    print("Embedding and indexing in ChromaDB...")
    _index_in_chromadb(store, progress_callback)
    print("Indexing complete.")
    if progress_callback:
        progress_callback(1, 1, "Indexing complete.")


def incremental_index(progress_callback: ProgressCallback = None) -> int:
    """Incremental indexing: only process new elements not yet in ChromaDB.

    Returns the number of new elements indexed.
    """
    if not DOCUMENT_STORE_PATH.exists():
        raise FileNotFoundError(
            "document_store.json not found. Run extract.py first."
        )

    store: dict = json.loads(DOCUMENT_STORE_PATH.read_text())

    # Phase 1: Generate VLM summaries for images with content=None
    _generate_vlm_summaries(store, progress_callback)

    # Phase 2: Get existing UUIDs from ChromaDB, only add new ones
    import chromadb
    from sentence_transformers import SentenceTransformer

    if progress_callback:
        progress_callback(0, 1, "Connecting to ChromaDB...")

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    try:
        collection = client.get_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        collection = client.create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # Get all existing IDs in the collection
    existing_ids = set()
    try:
        all_records = collection.get()
        existing_ids = set(all_records["ids"])
    except Exception:
        pass

    # Collect new elements that need embedding
    new_ids = []
    new_texts = []
    new_metadatas = []

    for uuid_, entry in store.items():
        content = entry["content"]
        if not content:
            continue
        if uuid_ in existing_ids:
            continue
        new_ids.append(uuid_)
        new_texts.append(content)
        new_metadatas.append({
            "uuid": uuid_,
            "type": entry["type"],
            "page": entry.get("page", 0),
            "path": entry.get("path") or "",
            "source_pdf": entry.get("source_pdf", ""),
        })

    if not new_ids:
        print("No new elements to index.")
        if progress_callback:
            progress_callback(1, 1, "No new elements to index.")
        return 0

    if progress_callback:
        progress_callback(0, len(new_ids), f"Embedding {len(new_ids)} new elements...")

    print(f"  Loading embedding model: {EMBEDDING_MODEL_NAME}")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print(f"  Batch embedding {len(new_ids)} new elements...")
    embeddings = embedder.encode(
        new_texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    ).tolist()

    collection.add(
        ids=new_ids,
        embeddings=embeddings,
        documents=new_texts,
        metadatas=new_metadatas,
    )
    print(f"  Indexed {len(new_ids)} new elements in ChromaDB")

    if progress_callback:
        progress_callback(len(new_ids), len(new_ids), f"Indexed {len(new_ids)} new elements.")

    return len(new_ids)


def _generate_vlm_summaries(store: dict, progress_callback: ProgressCallback = None) -> None:
    """Generate VLM summaries for images with content=None.

    Updates store in-place and saves to document_store.json periodically.
    """
    from PIL import Image as PILImage

    pending = []
    for uuid_, entry in store.items():
        if entry["type"] == "image" and entry["content"] is None:
            try:
                with PILImage.open(entry["path"]) as img:
                    w, h = img.size
                if w < 28 or h < 28:
                    print(f"  Skipping {Path(entry['path']).name} ({w}x{h}) — too small for VLM")
                    entry["content"] = f"[Image too small to process: {w}x{h}]"
                    continue
            except Exception as e:
                print(f"  Cannot read {entry['path']}: {e}, skipping")
                entry["content"] = f"[Unable to read image: {e}]"
                continue
            pending.append((uuid_, entry["path"]))

    if not pending:
        if progress_callback:
            progress_callback(1, 1, "No images need summarizing.")
        return

    print(f"  {len(pending)} images to summarize with {VLM_CONCURRENCY} concurrent workers...")
    client = _get_vlm_client()
    completed = 0
    total = len(pending)

    if progress_callback:
        progress_callback(0, total, f"Summarizing {total} images with VLM...")

    with ThreadPoolExecutor(max_workers=VLM_CONCURRENCY) as executor:
        futures = {
            executor.submit(_generate_image_summary, path, client): (uuid_, path)
            for uuid_, path in pending
        }
        for future in as_completed(futures):
            uuid_, path = futures[future]
            try:
                summary = future.result()
                store[uuid_]["content"] = summary
                print(f"  Summarized {Path(path).name}: {summary[:80]}...")
            except Exception as e:
                print(f"  Failed to summarize {Path(path).name}: {e}")
                store[uuid_]["content"] = f"[VLM summarization failed: {e}]"

            completed += 1
            if completed % VLM_SAVE_INTERVAL == 0:
                DOCUMENT_STORE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False))
                print(f"  Progress: {completed}/{total} (saved)")

            if progress_callback:
                progress_callback(completed, total, f"Summarized {completed}/{total} images")

    # Save updated store with summaries
    DOCUMENT_STORE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False))


def _get_vlm_client():
    """Create a single OpenAI client instance for reuse."""
    from openai import OpenAI
    return OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)


def _generate_image_summary(image_path: str, client=None) -> str:
    """Send image to Qwen-VL via SiliconFlow and get a text description."""
    if client is None:
        client = _get_vlm_client()

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    mime = mime_map.get(ext, "jpeg")

    response = client.chat.completions.create(
        model=VLM_MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": VLM_SUMMARY_PROMPT,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{mime};base64,{image_data}"
                        },
                    },
                ],
            }
        ],
        max_tokens=512,
        temperature=0.1,
    )

    return response.choices[0].message.content.strip()


def _index_in_chromadb(store: dict, progress_callback: ProgressCallback = None) -> None:
    """Embed all elements and index in ChromaDB with UUID metadata."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

    # Load embedding model
    print(f"  Loading embedding model: {EMBEDDING_MODEL_NAME}")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    # Delete existing collection if present (fresh reindex)
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Batch embed and insert
    ids = []
    texts = []
    metadatas = []

    for uuid_, entry in store.items():
        content = entry["content"]
        if not content:
            continue
        ids.append(uuid_)
        texts.append(content)
        metadatas.append({
            "uuid": uuid_,
            "type": entry["type"],
            "page": entry.get("page", 0),
            "path": entry.get("path") or "",
            "source_pdf": entry.get("source_pdf", ""),
        })

    if ids:
        if progress_callback:
            progress_callback(0, len(ids), f"Embedding {len(ids)} elements...")
        print(f"  Batch embedding {len(ids)} elements...")
        embeddings = embedder.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=True,
        ).tolist()

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"  Indexed {len(ids)} elements in ChromaDB")
        if progress_callback:
            progress_callback(len(ids), len(ids), f"Indexed {len(ids)} elements in ChromaDB")


if __name__ == "__main__":
    build_index()
