from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# ── Auth ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    email: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Community ─────────────────────────────────────────
class CommunityCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CommunityOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    join_code: str
    admin_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class JoinCommunityRequest(BaseModel):
    join_code: str


# ── Document ──────────────────────────────────────────
class DocumentOut(BaseModel):
    id: int
    community_id: int
    filename: str
    original_name: str
    file_size: int
    is_processed: bool
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ── Chat ──────────────────────────────────────────────
class ChatMessageCreate(BaseModel):
    community_id: int
    question: str


class ChatMessageOut(BaseModel):
    id: int
    user_id: int
    community_id: int
    role: str
    content: str
    source_doc: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Generic ───────────────────────────────────────────
class MessageResponse(BaseModel):
    message: str
