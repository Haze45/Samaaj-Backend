from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from ai.vector_store import load_store
from core.config import settings
from typing import Optional

# In-memory conversation history per user+community session
# Key: "{user_id}_{community_id}"
_memory_cache: dict = {}

SYSTEM_PROMPT = """You are SamaajBot, a helpful AI assistant for a community.
Answer the user's question using ONLY the context provided from community documents.
If the answer is not in the context, say: "I could not find this information in the community documents."
Be concise, clear and helpful. Always respond in the same language as the question.

Context from documents:
{context}

Chat history:
{chat_history}

Question: {question}
Answer:"""


def _get_memory(user_id: int, community_id: int) -> ConversationBufferWindowMemory:
    key = f"{user_id}_{community_id}"
    if key not in _memory_cache:
        _memory_cache[key] = ConversationBufferWindowMemory(
            k=5,
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
        )
    return _memory_cache[key]


def clear_memory(user_id: int, community_id: int):
    key = f"{user_id}_{community_id}"
    if key in _memory_cache:
        del _memory_cache[key]


def get_answer(question: str, community_id: int, user_id: int) -> dict:
    """
    Run RAG chain for a question against community ChromaDB collection.
    Returns: { "answer": str, "source": str | None }
    """
    # 1. Load ChromaDB store for this community
    store = load_store(community_id)
    if store is None:
        return {
            "answer": "No documents have been indexed for this community yet. Please ask your admin to upload documents.",
            "source": None,
        }

    # 2. Build retriever — fetch top 4 most relevant chunks
    retriever = store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},
    )

    # 3. Build Gemini LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        convert_system_message_to_human=True,
    )

    # 4. Custom prompt
    prompt = PromptTemplate(
        input_variables=["context", "chat_history", "question"],
        template=SYSTEM_PROMPT,
    )

    # 5. Per-user conversation memory
    memory = _get_memory(user_id, community_id)

    # 6. Build conversational RAG chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=True,
        output_key="answer",
        verbose=False,
    )

    # 7. Run and return
    result      = chain.invoke({"question": question})
    source_docs = result.get("source_documents", [])
    source      = source_docs[0].metadata.get("source_file") if source_docs else None

    return {
        "answer": result["answer"],
        "source": source,
    }
