from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from core.database import get_db, SessionLocal
from core.security import get_current_user
from core.config import settings
from ai.ingestion import ingest_document
from fcm_service import notify_new_document, notify_document_indexed
import models, schemas
import aiofiles, os, uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}

ALLOWED_EXTENSIONS_DISPLAY = "PDF (.pdf), Word (.docx), PowerPoint (.pptx)"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _require_membership(user_id: int, community_id: int, db: Session):
    m = db.query(models.Membership).filter_by(
        user_id=user_id, community_id=community_id
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this community")
    return m


def _require_admin(user_id: int, community_id: int, db: Session):
    community = db.query(models.Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if community.admin_id != user_id:
        raise HTTPException(status_code=403, detail="Only the admin can upload documents")
    return community


def _validate_file_type(content_type: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if content_type in ALLOWED_TYPES:
        return ALLOWED_TYPES[content_type]
    if ext in (".pdf", ".docx", ".pptx"):
        return ext
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS_DISPLAY}"
    )


def _get_community_member_tokens(community_id: int, db: Session) -> list[str]:
    """Get FCM tokens of all community members who have tokens set."""
    memberships = db.query(models.Membership).filter_by(
        community_id=community_id
    ).all()
    tokens = []
    for m in memberships:
        user = db.query(models.User).filter_by(id=m.user_id).first()
        if user and user.fcm_token:
            tokens.append(user.fcm_token)
    return tokens


def _run_ingestion(
    doc_id: int,
    community_id: int,
    filename: str,
    original_name: str,
    community_name: str,
):
    """
    Background task: embed document and send notifications.
    1. Ingest document into ChromaDB
    2. Mark as processed in DB
    3. Send push notification to all community members
    """
    db = SessionLocal()
    try:
        # Step 1: Ingest document into ChromaDB
        chunk_count = ingest_document(
            community_id=community_id,
            filename=filename,
            original_name=original_name,
        )

        # Step 2: Mark as processed
        doc = db.query(models.Document).filter_by(id=doc_id).first()
        if doc:
            doc.is_processed = True
            db.commit()

        # Step 3: Get all member tokens and send notification
        tokens = _get_community_member_tokens(community_id, db)
        notify_document_indexed(
            community_name=community_name,
            document_name=original_name,
            community_id=community_id,
            tokens=tokens,
        )

        print(f"[Ingestion] doc_id={doc_id} → {chunk_count} chunks, "
              f"notified {len(tokens)} members")

    except Exception as e:
        print(f"[Ingestion Error] doc_id={doc_id}: {e}")
    finally:
        db.close()


@router.post("/{community_id}/upload", response_model=schemas.DocumentOut, status_code=201)
async def upload_document(
    community_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    community = _require_admin(current_user.id, community_id, db)

    ext = _validate_file_type(file.content_type, file.filename)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(contents)

    doc = models.Document(
        community_id=community_id,
        uploaded_by=current_user.id,
        filename=unique_name,
        original_name=file.filename,
        file_size=len(contents),
        is_processed=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Immediately notify members about new upload (before indexing)
    tokens = _get_community_member_tokens(community_id, db)
    notify_new_document(
        community_name=community.name,
        document_name=file.filename,
        community_id=community_id,
        tokens=tokens,
    )

    # Start background indexing — sends another notification when done
    background_tasks.add_task(
        _run_ingestion,
        doc.id,
        community_id,
        unique_name,
        file.filename,
        community.name,
    )

    return doc


@router.get("/{community_id}", response_model=list[schemas.DocumentOut])
def list_documents(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_membership(current_user.id, community_id, db)
    return db.query(models.Document).filter_by(community_id=community_id).all()


@router.get("/{community_id}/{document_id}/download")
def download_document(
    community_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_membership(current_user.id, community_id, db)
    doc = db.query(models.Document).filter_by(
        id=document_id, community_id=community_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on server")

    media_types = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    ext = os.path.splitext(doc.filename)[1].lower()
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type, filename=doc.original_name)


@router.delete("/{community_id}/{document_id}", response_model=schemas.MessageResponse)
def delete_document(
    community_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_admin(current_user.id, community_id, db)
    doc = db.query(models.Document).filter_by(
        id=document_id, community_id=community_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}