import hashlib
import math
import re

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import database_url
from .models import Document, DocumentChunk
from .schemas import Citation

DIMENSIONS = 1536


def _local_embedding(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in re.findall(r"[a-zA-Z0-9À-ÿ]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % DIMENSIONS
        vector[bucket] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed(texts: list[str]) -> tuple[list[list[float]], str]:
    settings = get_settings()
    if not settings.openai_api_key:
        return [_local_embedding(text) for text in texts], "local-embedding"
    response = OpenAI(api_key=settings.openai_api_key).embeddings.create(
        model=settings.openai_embedding_model, input=texts, dimensions=DIMENSIONS
    )
    return [item.embedding for item in response.data], "openai-embedding"


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def retrieve(db: Session, workspace_id: str, question: str, limit: int = 4) -> list[tuple[DocumentChunk, Document, float]]:
    query_vector = embed([question])[0][0]
    if database_url.startswith("postgresql"):
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = db.execute(
            select(DocumentChunk, Document, (1 - distance).label("similarity"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.workspace_id == workspace_id)
            .order_by(distance).limit(limit)
        ).all()
        return [(chunk, document, float(score)) for chunk, document, score in rows if score > 0.05]
    rows = db.execute(
        select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.workspace_id == workspace_id)
    ).all()
    ranked = sorted(
        ((chunk, document, _cosine(query_vector, chunk.embedding)) for chunk, document in rows),
        key=lambda item: item[2], reverse=True,
    )
    return [item for item in ranked[:limit] if item[2] > 0.01]


def make_citations(matches: list[tuple[DocumentChunk, Document, float]]) -> list[Citation]:
    return [Citation(
        document_id=document.id, title=document.title,
        excerpt=(chunk.content[:240] + "…") if len(chunk.content) > 240 else chunk.content,
        page_number=chunk.page_number, similarity=round(score, 3),
    ) for chunk, document, score in matches]


def answer(question: str, matches: list[tuple[DocumentChunk, Document, float]]) -> tuple[str, str]:
    if not matches:
        return "I couldn't find enough workspace evidence to answer that question.", "grounded-local"
    settings = get_settings()
    if not settings.openai_api_key:
        chunk, document, _ = matches[0]
        return f"Based on “{document.title}”: {chunk.content[:520].strip()}", "grounded-local"
    context = "\n\n".join(
        f"SOURCE {index + 1} — {document.title}, page {chunk.page_number or 'n/a'}\n{chunk.content}"
        for index, (chunk, document, _) in enumerate(matches)
    )
    response = OpenAI(api_key=settings.openai_api_key).responses.create(
        model=settings.openai_model,
        instructions="Answer only from supplied sources. Cite claims with [1], [2]. Never invent policy.",
        input=f"Question: {question}\n\nSources:\n{context}",
    )
    return response.output_text, "openai-grounded"
