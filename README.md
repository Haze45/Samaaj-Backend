# SamaajBot — AI-Powered Community Document Assistant

> Ask questions about your community documents in natural language and get instant AI-powered answers with source citations.

---

## What is SamaajBot?

SamaajBot is a full-stack mobile application that allows communities (housing societies, NGOs, student groups, local organizations) to upload important documents and let members ask questions about them using natural language.

**Admin uploads a PDF/DOCX/PPTX → AI indexes it → Members ask questions → AI answers from the document**

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| Python 3.11 | Backend language |
| FastAPI | REST API framework |
| SQLite + SQLAlchemy | Relational database |
| LangChain 0.3 | AI orchestration |
| ChromaDB | Vector database |
| Google Gemini 2.5 Flash | LLM for answers |
| Gemini Embedding 001 | Document embeddings |
| Hybrid RAG (MMR + BM25) | Advanced retrieval |
| Firebase Admin SDK | Push notifications |
| Docker | Containerization |
| Render.com | Cloud deployment |

### Android App
| Technology | Purpose |
|---|---|
| Kotlin | Programming language |
| Jetpack Compose | Modern UI framework |
| Hilt | Dependency injection |
| Retrofit + OkHttp | Network layer |
| Room Database | Local chat cache |
| DataStore | JWT token storage |
| Firebase Messaging | Push notifications |
| Navigation Compose | Screen navigation |

---

## Features

- **Multi-community support** — create or join communities with unique 7-character codes
- **Role-based access** — Admins upload documents, Members ask questions
- **Multi-format documents** — supports PDF, Word (.docx) and PowerPoint (.pptx)
- **Advanced RAG pipeline** — Hybrid search (Dense MMR + Sparse BM25) for accurate answers
- **Source citation** — every AI answer shows which document it came from
- **Chat history** — persistent across devices, synced from server
- **Push notifications** — notify members on new document upload and indexing
- **Voice input** — ask questions by speaking
- **Dark mode** — full Material Design 3 with dark mode support

---

## Project Structure

```
samaajbot/
├── main.py                  ← FastAPI entry point
├── models.py                ← SQLAlchemy database models
├── schemas.py               ← Pydantic request/response schemas
├── fcm_service.py           ← Firebase push notification service
├── requirements.txt
├── Dockerfile
├── render.yaml
│
├── core/
│   ├── config.py            ← App settings
│   ├── database.py          ← SQLite engine
│   └── security.py          ← JWT authentication
│
├── ai/
│   ├── custom_loaders.py    ← python-docx and python-pptx loaders
│   ├── ingestion.py         ← PDF/DOCX/PPTX ingestion pipeline
│   ├── vector_store.py      ← ChromaDB operations
│   ├── retriever.py         ← MMR + BM25 + Hybrid retriever
│   └── rag.py               ← RAG chain with Gemini
│
└── routers/
    ├── auth.py              ← Register, login, FCM token
    ├── communities.py       ← Create, join, list, leave
    ├── documents.py         ← Upload, list, delete documents
    └── chat.py              ← Ask questions, chat history
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Login and get JWT token |
| GET | `/auth/me` | Get current user |
| POST | `/auth/fcm-token` | Update FCM push token |

### Communities
| Method | Endpoint | Description |
|---|---|---|
| POST | `/communities` | Create community |
| POST | `/communities/join` | Join via code |
| GET | `/communities` | List my communities |
| GET | `/communities/{id}` | Get community details |
| DELETE | `/communities/{id}/leave` | Leave community |

### Documents
| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents/{id}/upload` | Upload PDF/DOCX/PPTX |
| GET | `/documents/{id}` | List community documents |
| GET | `/documents/{id}/{doc_id}/download` | Download document |
| DELETE | `/documents/{id}/{doc_id}` | Delete document |

### Chat
| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat/ask` | Ask a question |
| GET | `/chat/history/{id}` | Get chat history |
| DELETE | `/chat/history/{id}` | Clear chat history |

---

## RAG Pipeline

```
PDF / DOCX / PPTX upload
        ↓
Custom loader (PyPDFLoader / python-docx / python-pptx)
        ↓
RecursiveCharacterTextSplitter (800 chars, 100 overlap)
        ↓
Gemini Embedding 001 → 768-dim vectors
        ↓
ChromaDB persistent storage
        ↓
User asks question
        ↓
Hybrid Retriever:
  ├── Level 1: MMR (diverse semantic search)
  ├── Level 2: BM25 (exact keyword search)
  └── Level 3: EnsembleRetriever (RRF reranking)
        ↓
Top 4 chunks → Gemini 2.5 Flash
        ↓
Grounded answer + source citation
```

---

## Local Development Setup

### Prerequisites
- Python 3.11
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Haze45/samaajbot-backend.git
cd samaajbot-backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 5. Run the server
uvicorn main:app --reload

# 6. Open Swagger docs
# http://localhost:8000/docs
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key from aistudio.google.com |
| `SECRET_KEY` | ✅ Yes | Random string for JWT signing |
| `DATABASE_URL` | No | SQLite URL (default: `sqlite:///./samaajbot.db`) |
| `UPLOAD_DIR` | No | PDF storage folder (default: `./uploads`) |
| `CHROMA_DIR` | No | ChromaDB storage folder (default: `./chroma_db`) |
| `FIREBASE_CREDENTIALS_JSON` | No | Firebase service account JSON for push notifications |

---

## Deployment on Render

```bash
# 1. Push to GitHub
git add .
git commit -m "initial commit"
git push -u origin master

# 2. Go to render.com
# New → Web Service → Connect GitHub repo
# Runtime: Docker
# Plan: Free

# 3. Add environment variables on Render dashboard
# GEMINI_API_KEY = your key
# FIREBASE_CREDENTIALS_JSON = paste service account JSON

# 4. Add persistent disk
# Mount path: /app/data
# Size: 1 GB

# 5. Deploy — get public URL like:
# https://samaajbot-api.onrender.com
```

---

## Android App Setup

1. Open `SamaajBot/` in Android Studio
2. Place `google-services.json` in `app/` folder
3. Update `BASE_URL` in `utils/Constants.kt`:
```kotlin
const val BASE_URL = "https://samaajbot-api.onrender.com/"
```
4. Sync Gradle → Run

---

## Push Notifications

SamaajBot sends push notifications via Firebase Cloud Messaging (FCM) for:

| Event | Recipients |
|---|---|
| New document uploaded | All community members |
| Document indexed and ready | All community members |
| New member joins | Community admin only |

---



