from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from core.database import get_db, SessionLocal
from core.security import get_current_user
from core.config import settings
from ai.ingestion import ingest_pdf
import models, schemas
import aiofiles, os, uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {"application/pdf"}
MAX_FILE_SIZE  = 10 * 1024 * 1024  # 10 MB


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


def _run_ingestion(doc_id: int, community_id: int, filename: str):
    """
    Background task: embed PDF into ChromaDB and mark document as processed.
    Uses its own DB session since it runs outside the request lifecycle.
    """
    db = SessionLocal()
    try:
        ingest_pdf(community_id=community_id, filename=filename)
        doc = db.query(models.Document).filter_by(id=doc_id).first()
        if doc:
            doc.is_processed = True
            db.commit()
    except Exception as e:
        print(f"[ChromaDB Ingestion Error] doc_id={doc_id}: {e}")
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
    _require_admin(current_user.id, community_id, db)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    ext         = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path   = os.path.join(settings.UPLOAD_DIR, unique_name)

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

    # Kick off ChromaDB embedding in background
    background_tasks.add_task(_run_ingestion, doc.id, community_id, unique_name)

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

    return FileResponse(file_path, media_type="application/pdf", filename=doc.original_name)


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
