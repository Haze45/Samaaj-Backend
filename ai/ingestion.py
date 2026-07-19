import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ai.vector_store import add_documents_to_store
from ai.custom_loaders import load_docx, load_pptx
from core.config import settings


def _load_by_extension(file_path: str, original_name: str) -> list:
    """
    Routes the file to the correct loader based on its extension:
      .pdf  -> LangChain's PyPDFLoader (built-in, works well for PDFs)
      .docx -> custom python-docx loader (preserves table structure)
      .pptx -> custom python-pptx loader (reads every slide and table)
    Raises ValueError for any other extension.
    """
    ext = os.path.splitext(original_name)[1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
        return loader.load()

    elif ext == ".docx":
        return load_docx(file_path)

    elif ext == ".pptx":
        return load_pptx(file_path)

    else:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported types: .pdf, .docx, .pptx"
        )


def ingest_document(community_id: int, filename: str, original_name: str) -> int:
    """
    Load a document (PDF, DOCX, or PPTX), split into chunks, embed and
    store in ChromaDB. Returns the number of chunks created.
    Automatically called as a background task after a document is uploaded.
    """
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    # 1. Load document content using the correct loader for its file type
    pages = _load_by_extension(file_path, original_name)

    # 2. Split into overlapping chunks for better retrieval
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(pages)

    # 3. Tag each chunk with metadata for citation
    for chunk in chunks:
        chunk.metadata["community_id"] = community_id
        chunk.metadata["source_file"] = original_name

    # 4. Embed and persist in ChromaDB
    add_documents_to_store(community_id, chunks)

    return len(chunks)


# Kept for backward compatibility - old code calling ingest_pdf() still works
def ingest_pdf(community_id: int, filename: str) -> int:
    """Deprecated alias - use ingest_document instead."""
    return ingest_document(community_id, filename, filename)