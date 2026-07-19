"""
Advanced retriever module implementing three levels of search:

Level 1 - MMR (Maximal Marginal Relevance)
    Uses ChromaDB built-in MMR to retrieve relevant AND diverse chunks.

Level 2 - Sparse Search (BM25)
    Classic keyword-based search using BM25 algorithm.
    Excellent for exact terms, rule numbers, specific codes.

Level 3 - Hybrid Search with Reranking
    Combines Dense (ChromaDB vector) + Sparse (BM25) retrievers using
    LangChain EnsembleRetriever with Reciprocal Rank Fusion.
"""

import re
import logging
from langchain_community.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from ai.vector_store import load_store, get_all_documents

logger = logging.getLogger(__name__)

# Search configuration
TOP_K        = 4     # final chunks sent to LLM
MMR_FETCH_K  = 20    # MMR candidate pool
MMR_LAMBDA   = 0.6   # 0=max diversity, 1=max relevance
DENSE_WEIGHT = 0.6   # weight for vector search
SPARSE_WEIGHT = 0.4  # weight for BM25 search


def get_mmr_retriever(community_id: int):
    """
    Level 1: MMR retriever.
    Fetches diverse and relevant chunks from ChromaDB.
    Prevents returning 4 chunks that all say the same thing.
    """
    store = load_store(community_id)
    if store is None:
        return None

    return store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k":           TOP_K,
            "fetch_k":     MMR_FETCH_K,
            "lambda_mult": MMR_LAMBDA,
        }
    )


def get_sparse_retriever(community_id: int):
    """
    Level 2: BM25 sparse keyword retriever.
    Best for exact rule numbers, names, codes, specific terms.
    """
    all_docs = get_all_documents(community_id)
    if not all_docs:
        return None

    retriever = BM25Retriever.from_documents(all_docs)
    retriever.k = TOP_K
    return retriever


def get_hybrid_retriever(community_id: int):
    """
    Level 3: Hybrid Dense + Sparse retriever with Reciprocal Rank Fusion.

    Combines ChromaDB MMR (dense) and BM25 (sparse) results.
    RRF formula: score = sum(1 / (rank + 60)) across all retrievers.
    Documents ranking well in BOTH retrievers get highest final score.
    """
    store = load_store(community_id)
    if store is None:
        return None

    all_docs = get_all_documents(community_id)
    if not all_docs:
        return None

    dense_retriever = store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k":           TOP_K * 2,
            "fetch_k":     MMR_FETCH_K,
            "lambda_mult": MMR_LAMBDA,
        }
    )

    sparse_retriever = BM25Retriever.from_documents(all_docs)
    sparse_retriever.k = TOP_K * 2

    return EnsembleRetriever(
        retrievers=[dense_retriever, sparse_retriever],
        weights=[DENSE_WEIGHT, SPARSE_WEIGHT],
        c=60,
    )


def get_best_retriever(community_id: int, question: str):
    """
    Auto-selects the best retriever based on question analysis.

    If question contains specific terms (rule numbers, amounts, codes)
    -> use Hybrid (Dense + Sparse) for best accuracy.

    If question is conceptual/general
    -> use MMR for diverse relevant context.
    """
    specific_indicators = [
        "rule", "section", "clause", "article", "point",
        "rs.", "rs ", "rupee", "form", "schedule", "bylaw",
    ]

    question_lower = question.lower()
    has_specific_terms = any(k in question_lower for k in specific_indicators)
    has_numbers = bool(re.search(r'\d+', question))

    if has_specific_terms or has_numbers:
        logger.info(f"[Auto] Hybrid retriever selected for: {question[:60]}")
        retriever = get_hybrid_retriever(community_id)
        if retriever:
            return retriever

    logger.info(f"[Auto] MMR retriever selected for: {question[:60]}")
    return get_mmr_retriever(community_id)