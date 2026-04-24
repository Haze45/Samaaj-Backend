from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_user
import models, schemas
import random, string

router = APIRouter(prefix="/communities", tags=["Communities"])


def _generate_join_code(length: int = 7) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@router.post("", response_model=schemas.CommunityOut, status_code=201)
def create_community(
    payload: schemas.CommunityCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    code = _generate_join_code()
    while db.query(models.Community).filter(models.Community.join_code == code).first():
        code = _generate_join_code()

    community = models.Community(
        name=payload.name,
        description=payload.description,
        join_code=code,
        admin_id=current_user.id,
    )
    db.add(community)
    db.flush()

    db.add(models.Membership(user_id=current_user.id, community_id=community.id))
    db.commit()
    db.refresh(community)
    return community


@router.post("/join", response_model=schemas.CommunityOut)
def join_community(
    payload: schemas.JoinCommunityRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    community = db.query(models.Community).filter(
        models.Community.join_code == payload.join_code
    ).first()
    if not community:
        raise HTTPException(status_code=404, detail="Invalid join code")

    already = db.query(models.Membership).filter_by(
        user_id=current_user.id, community_id=community.id
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Already a member")

    db.add(models.Membership(user_id=current_user.id, community_id=community.id))
    db.commit()
    return community


@router.get("", response_model=list[schemas.CommunityOut])
def my_communities(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    memberships = db.query(models.Membership).filter_by(user_id=current_user.id).all()
    return [m.community for m in memberships]


@router.get("/{community_id}", response_model=schemas.CommunityOut)
def get_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = db.query(models.Membership).filter_by(
        user_id=current_user.id, community_id=community_id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this community")
    return membership.community


@router.delete("/{community_id}/leave", response_model=schemas.MessageResponse)
def leave_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = db.query(models.Membership).filter_by(
        user_id=current_user.id, community_id=community_id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    community = db.query(models.Community).filter_by(id=community_id).first()
    if community.admin_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot leave. Delete the community instead."
        )

    db.delete(membership)
    db.commit()
    return {"message": "Left community successfully"}
