from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import engine, Base
import models

from routers import auth, communities, documents, chat

# Create all SQLite tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for SamaajBot — AI-powered community document assistant using ChromaDB",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(communities.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": settings.APP_NAME, "vector_db": "ChromaDB"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
