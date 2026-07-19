"""
RAG (Retrieval Augmented Generation) chain module.

Uses the advanced hybrid retriever (Dense MMR + Sparse BM25) to fetch
the most relevant document chunks, then generates grounded answers
using Google Gemini.

Pipeline:
  1. User question
  2. Hybrid retriever fetches relevant + diverse chunks
     (Level 1: MMR for diversity)
     (Level 2: BM25 for exact keyword matching)
     (Level 3: EnsembleRetriever combines both with RRF reranking)
  3. Retrieved chunks + chat history passed to Gemini prompt
  4. Gemini generates answer grounded in document context
  5. Source document cited in response
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from ai.retriever import get_best_retriever
from core.config import settings

# In-memory conversation history per user+community session
# Key: "{user_id}_{community_id}"
_history_cache: dict = {}

SYSTEM_PROMPT = """You are SamaajBot, a helpful AI assistant for a community.
Answer the user's question using ONLY the context provided from community documents.
If the answer is not in the context, say: "I could not find this information in the community documents."
Be concise, clear and helpful. Always respond in the same language as the question.
When answering, prioritize the most specific and relevant information from the context.

Context from documents:
{context}"""


def _get_history(user_id: int, community_id: int) -> list:
    key = f"{user_id}_{community_id}"
    if key not in _history_cache:
        _history_cache[key] = []
    return _history_cache[key]


def _add_to_history(user_id: int, community_id: int, question: str, answer: str):
    history = _get_history(user_id, community_id)
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    # Keep only last 5 exchanges (10 messages)
    if len(history) > 10:
        _history_cache[f"{user_id}_{community_id}"] = history[-10:]


def clear_memory(user_id: int, community_id: int):
    key = f"{user_id}_{community_id}"
    if key in _history_cache:
        del _history_cache[key]


def get_answer(
    question: str,
    community_id: int,
    user_id: int,
    retriever_mode: str = "hybrid"
) -> dict:
    """
    Run the full RAG pipeline with hybrid search.

    retriever_mode options:
      "similarity" — basic vector similarity (original)
      "mmr"        — Level 1: MMR diversity search
      "sparse"     — Level 2: BM25 keyword search
      "hybrid"     — Level 3: Dense MMR + Sparse BM25 (default, best)

    Returns: { "answer": str, "source": str | None, "retriever_mode": str }
    """
    # 1. Get the best retriever for this community
    retriever = get_best_retriever(
        community_id=community_id,
        k=4,
        mode=retriever_mode
    )

    if retriever is None:
        return {
            "answer": "No documents have been indexed for this community yet. "
                      "Please ask your admin to upload documents.",
            "source": None,
            "retriever_mode": retriever_mode,
        }

    # 2. Build Gemini LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
    )

    # 3. Build prompt with chat history support
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    # 4. Get conversation history
    history = _get_history(user_id, community_id)

    # 5. Retrieve relevant chunks using hybrid search
    source_docs = retriever.invoke(question)

    # 6. Format context from retrieved chunks
    context = "\n\n".join([
        f"[Source: {doc.metadata.get('source_file', 'unknown')}]\n{doc.page_content}"
        for doc in source_docs
    ])

    # 7. Build and run LCEL chain
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({
        "input": question,
        "context": context,
        "chat_history": history,
    })

    # 8. Save to conversation history
    _add_to_history(user_id, community_id, question, answer)

    # 9. Extract source from top retrieved document
    source = None
    if source_docs:
        source = source_docs[0].metadata.get("source_file")

    return {
        "answer": answer,
        "source": source,
        "retriever_mode": retriever_mode,
    }