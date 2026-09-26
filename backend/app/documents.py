from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader


def extract_pages(filename: str, mime_type: str, data: bytes) -> list[tuple[int | None, str]]:
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(data))
            pages = [(index + 1, (page.extract_text() or "").strip()) for index, page in enumerate(reader.pages)]
            return [(number, text) for number, text in pages if text]
        except Exception as exc:
            raise HTTPException(status_code=400, detail="The PDF could not be read") from exc
    if mime_type.startswith("text/") or filename.lower().endswith((".txt", ".md")):
        try:
            text = data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Text files must use UTF-8") from exc
        return [(None, text)] if text else []
    raise HTTPException(status_code=415, detail="Supported files: PDF, TXT, and Markdown")


def chunk_pages(pages: list[tuple[int | None, str]], size: int = 900, overlap: int = 140) -> list[tuple[int | None, str]]:
    chunks: list[tuple[int | None, str]] = []
    for page, text in pages:
        clean = " ".join(text.split())
        start = 0
        while start < len(clean):
            end = min(start + size, len(clean))
            if end < len(clean):
                boundary = clean.rfind(" ", start, end)
                if boundary > start + size // 2:
                    end = boundary
            value = clean[start:end].strip()
            if value:
                chunks.append((page, value))
            if end >= len(clean):
                break
            start = max(end - overlap, start + 1)
    return chunks
