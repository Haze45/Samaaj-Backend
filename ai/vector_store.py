from typing import Optional
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from core.config import settings


def _embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GEMINI_API_KEY,
    )


def _collection_name(community_id: int) -> str:
    return f"community_{community_id}"


def load_store(community_id: int) -> Optional[Chroma]:
    """Load ChromaDB collection for a community. Returns None if empty."""
    store = Chroma(
        collection_name=_collection_name(community_id),
        embedding_function=_embeddings(),
        persist_directory=settings.CHROMA_DIR,
    )
    # chromadb 1.x uses .count() directly on the collection
    try:
        count = store._collection.count()
    except Exception:
        count = 0
    if count == 0:
        return None
    return store


def add_documents_to_store(community_id: int, chunks: list):
    """Embed document chunks and store in ChromaDB."""
    Chroma.from_documents(
        documents=chunks,
        embedding=_embeddings(),
        collection_name=_collection_name(community_id),
        persist_directory=settings.CHROMA_DIR,
    )


def delete_store(community_id: int):
    """Delete entire ChromaDB collection for a community."""
    store = Chroma(
        collection_name=_collection_name(community_id),
        embedding_function=_embeddings(),
        persist_directory=settings.CHROMA_DIR,
    )
    store.delete_collection()
