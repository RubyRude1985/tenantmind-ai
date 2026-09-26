import re
from collections.abc import Generator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .auth import create_token, current_user, hash_password, verify_password
from .config import get_settings
from .database import Base, SessionLocal, engine, prepare_database
from .documents import chunk_pages, extract_pages
from .models import AuditEvent, Document, DocumentChunk, User, Workspace
from .rag import answer, embed, make_citations, retrieve
from .schemas import AuthResponse, ChatRequest, ChatResponse, DashboardStats, DocumentCreate, DocumentRead, LoginRequest, RegisterRequest

settings = get_settings()
prepare_database()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TenantMind AI API", version="2.0.0", description="Secure multi-tenant RAG assistant with PDF ingestion and cited answers.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def workspace_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "workspace"


def log_event(db: Session, user: User, action: str, details: str = "") -> None:
    db.add(AuditEvent(workspace_id=user.workspace_id, user_id=user.id, action=action, details=details[:300]))


def auth_response(db: Session, user: User) -> AuthResponse:
    workspace = db.get(Workspace, user.workspace_id)
    return AuthResponse(access_token=create_token(user), user_name=user.name, workspace_name=workspace.name if workspace else "Workspace")


def persist_document(db: Session, user: User, title: str, filename: str | None, mime_type: str, pages: list[tuple[int | None, str]]) -> Document:
    chunks = chunk_pages(pages)
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text was found")
    vectors, _ = embed([content for _, content in chunks])
    document = Document(
        workspace_id=user.workspace_id, title=title, filename=filename, mime_type=mime_type,
        content="\n\n".join(text for _, text in pages), status="ready", chunk_count=len(chunks),
    )
    db.add(document)
    db.flush()
    for index, ((page_number, content), vector) in enumerate(zip(chunks, vectors)):
        db.add(DocumentChunk(
            document_id=document.id, workspace_id=user.workspace_id, content=content,
            page_number=page_number, chunk_index=index, embedding=vector,
        ))
    log_event(db, user, "document.created", title)
    db.commit()
    db.refresh(document)
    return document


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tenantmind-api", "version": "2.0.0"}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    base_slug, suffix = workspace_slug(payload.workspace_name), 2
    slug = base_slug
    while db.scalar(select(Workspace).where(Workspace.slug == slug)):
        slug, suffix = f"{base_slug}-{suffix}", suffix + 1
    workspace = Workspace(name=payload.workspace_name.strip(), slug=slug)
    db.add(workspace)
    db.flush()
    user = User(workspace_id=workspace.id, name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_response(db, user)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return auth_response(db, user)


@app.post("/api/auth/demo", response_model=AuthResponse)
def demo_login(db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == "demo@tenantmind.local"))
    if user is None:
        workspace = Workspace(name="Northstar Operations", slug="northstar-demo")
        db.add(workspace)
        db.flush()
        user = User(workspace_id=workspace.id, name="Demo Analyst", email="demo@tenantmind.local", password_hash=hash_password("demo-password"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return auth_response(db, user)


@app.get("/api/documents", response_model=list[DocumentRead])
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.workspace_id == user.workspace_id).order_by(Document.created_at.desc())))


@app.post("/api/documents/text", response_model=DocumentRead, status_code=201)
def create_text_document(payload: DocumentCreate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Document:
    return persist_document(db, user, payload.title, None, "text/plain", [(None, payload.content)])


@app.post("/api/documents/upload", response_model=DocumentRead, status_code=201)
async def upload_document(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)) -> Document:
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum file size is 8 MB")
    filename = file.filename or "document"
    mime_type = file.content_type or "application/octet-stream"
    pages = extract_pages(filename, mime_type, data)
    title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    return persist_document(db, user, title, filename, mime_type, pages)


@app.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.workspace_id == user.workspace_id))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    log_event(db, user, "document.deleted", document.title)
    db.commit()


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ChatResponse:
    matches = retrieve(db, user.workspace_id, payload.question)
    response_text, mode = answer(payload.question, matches)
    log_event(db, user, "question.asked", payload.question)
    db.commit()
    return ChatResponse(answer=response_text, citations=make_citations(matches), mode=mode)


@app.get("/api/dashboard", response_model=DashboardStats)
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)) -> DashboardStats:
    documents = db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == user.workspace_id)) or 0
    chunks = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.workspace_id == user.workspace_id)) or 0
    questions = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.workspace_id == user.workspace_id, AuditEvent.action == "question.asked")) or 0
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == user.workspace_id).order_by(AuditEvent.created_at.desc()).limit(5)))
    return DashboardStats(
        documents=documents, chunks=chunks, questions=questions,
        latest_activity=[{"action": e.action, "details": e.details, "created_at": e.created_at.isoformat()} for e in events],
    )
