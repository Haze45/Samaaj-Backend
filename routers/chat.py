from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_user
from ai.rag import get_answer, clear_memory
import models, schemas

router = APIRouter(prefix="/chat", tags=["Chat"])


def _require_membership(user_id: int, community_id: int, db: Session):
    m = db.query(models.Membership).filter_by(
        user_id=user_id, community_id=community_id
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this community")


@router.post("/ask", response_model=schemas.ChatMessageOut)
def ask_question(
    payload: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_membership(current_user.id, payload.community_id, db)

    # Ensure at least one processed document exists in ChromaDB
    doc_count = db.query(models.Document).filter_by(
        community_id=payload.community_id, is_processed=True
    ).count()
    if doc_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No indexed documents found. Please upload and wait for documents to be processed."
        )

    # Save user question to DB
    user_msg = models.ChatMessage(
        user_id=current_user.id,
        community_id=payload.community_id,
        role="user",
        content=payload.question,
    )
    db.add(user_msg)
    db.flush()

    # ── ChromaDB RAG Call ─────────────────────────────────────────────────────
    try:
        result = get_answer(
            question=payload.question,
            community_id=payload.community_id,
            user_id=current_user.id,
        )
        answer_text = result["answer"]
        source_doc  = result["source"]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")
    # ─────────────────────────────────────────────────────────────────────────

    # Save assistant answer to DB
    bot_msg = models.ChatMessage(
        user_id=current_user.id,
        community_id=payload.community_id,
        role="assistant",
        content=answer_text,
        source_doc=source_doc,
    )
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)
    return bot_msg


@router.get("/history/{community_id}", response_model=list[schemas.ChatMessageOut])
def get_history(
    community_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_membership(current_user.id, community_id, db)

    messages = (
        db.query(models.ChatMessage)
        .filter_by(user_id=current_user.id, community_id=community_id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


@router.delete("/history/{community_id}", response_model=schemas.MessageResponse)
def clear_history(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_membership(current_user.id, community_id, db)

    db.query(models.ChatMessage).filter_by(
        user_id=current_user.id,
        community_id=community_id
    ).delete()
    db.commit()

    # Also clear in-memory LangChain conversation history
    clear_memory(user_id=current_user.id, community_id=community_id)

    return {"message": "Chat history cleared"}
