import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ai.vector_store import add_documents_to_store
from core.config import settings


def ingest_pdf(community_id: int, filename: str) -> int:
    """
    Load a PDF, split into chunks, embed and store in ChromaDB.
    Returns the number of chunks created.
    """
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    # 1. Load all pages from PDF
    loader = PyPDFLoader(file_path)
    pages  = loader.load()

    # 2. Split into overlapping chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(pages)

    # 3. Tag each chunk with metadata for citation
    for chunk in chunks:
        chunk.metadata["community_id"] = community_id
        chunk.metadata["source_file"]  = filename

    # 4. Embed and persist in ChromaDB
    add_documents_to_store(community_id, chunks)

    return len(chunks)
