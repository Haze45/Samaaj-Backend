from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(100), nullable=False)
    email            = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password  = Column(String, nullable=False)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    memberships      = relationship("Membership", back_populates="user")
    chat_messages    = relationship("ChatMessage", back_populates="user")


class Community(Base):
    __tablename__ = "communities"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    join_code   = Column(String(10), unique=True, index=True, nullable=False)
    admin_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    admin       = relationship("User", foreign_keys=[admin_id])
    memberships = relationship("Membership", back_populates="community")
    documents   = relationship("Document", back_populates="community")


class Membership(Base):
    __tablename__ = "memberships"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    joined_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user         = relationship("User", back_populates="memberships")
    community    = relationship("Community", back_populates="memberships")


class Document(Base):
    __tablename__ = "documents"

    id            = Column(Integer, primary_key=True, index=True)
    community_id  = Column(Integer, ForeignKey("communities.id"), nullable=False)
    uploaded_by   = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename      = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_size     = Column(Integer, nullable=False)
    is_processed  = Column(Boolean, default=False)
    uploaded_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    community     = relationship("Community", back_populates="documents")
    uploader      = relationship("User", foreign_keys=[uploaded_by])


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    role         = Column(String(10), nullable=False)   # "user" or "assistant"
    content      = Column(Text, nullable=False)
    source_doc   = Column(String(255), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user         = relationship("User", back_populates="chat_messages")
