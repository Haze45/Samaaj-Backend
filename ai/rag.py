from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from ai.vector_store import load_store
from core.config import settings
from typing import Optional

# In-memory conversation history per user+community
# Key: "{user_id}_{community_id}"
_history_cache: dict = {}

SYSTEM_PROMPT = """You are SamaajBot, a helpful AI assistant for a community.
Answer the user's question using ONLY the context provided from community documents.
If the answer is not in the context, say: "I could not find this information in the community documents."
Be concise, clear and helpful. Always respond in the same language as the question.

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


def get_answer(question: str, community_id: int, user_id: int) -> dict:
    """
    Run RAG chain using LangChain 0.3 LCEL style.
    Returns: { "answer": str, "source": str | None }
    """
    # 1. Load ChromaDB store
    store = load_store(community_id)
    if store is None:
        return {
            "answer": "No documents have been indexed for this community yet. Please ask your admin to upload documents.",
            "source": None,
        }

    # 2. Build retriever
    retriever = store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},
    )

    # 3. Build Gemini LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
    )

    # 4. Build prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    # 5. Get conversation history
    history = _get_history(user_id, community_id)

    # 6. Retrieve relevant docs
    source_docs = retriever.invoke(question)
    context = "\n\n".join([doc.page_content for doc in source_docs])

    # 7. Build and run chain using LCEL pipe style
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({
        "input": question,
        "context": context,
        "chat_history": history,
    })

    # 8. Save to history
    _add_to_history(user_id, community_id, question, answer)

    # 9. Extract source
    source = source_docs[0].metadata.get("source_file") if source_docs else None

    return {
        "answer": answer,
        "source": source,
    }
