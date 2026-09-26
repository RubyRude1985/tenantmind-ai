from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=50_000)


class DocumentRead(BaseModel):
    id: str
    title: str
    filename: str | None
    mime_type: str
    status: str
    chunk_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


class Citation(BaseModel):
    document_id: str
    title: str
    excerpt: str
    page_number: int | None = None
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    mode: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    workspace_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    workspace_name: str


class DashboardStats(BaseModel):
    documents: int
    chunks: int
    questions: int
    latest_activity: list[dict[str, str]]
