import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import chunk_text
from app.db import get_db
from app.extraction import ExtractionError, extract_text
from app.models import Document, DocumentChunk
from app.permissions import OrgMember, TenantDb
from app.storage import Storage, get_storage

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
Dbsession = Annotated[AsyncSession, Depends(get_db)]
StorageDep = Annotated[Storage, Depends(get_storage)]

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB
CHUNK_SIZE = 64 * 1024  # 64KB


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    filename: str
    content_type: str
    size_bytes: int
    content_hash: str


class ChunkOut(BaseModel):
    chunk_index: int
    text: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentOut)
async def upload_document(
    ctx: OrgMember,
    file: Annotated[UploadFile, File(...)],
    db: TenantDb,
    storage: StorageDep,
) -> Document:
    # --- 1. Validate declared content type ---
    content_type = file.content_type
    if content_type is None or content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type: {content_type}",
        )

    # --- 2. Read in blocks: enforce size limit, hash, keep the bytes ---
    hasher = hashlib.sha256()
    parts: list[bytes] = []
    size_bytes = 0
    while block := await file.read(CHUNK_SIZE):
        size_bytes += len(block)
        if size_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            )
        hasher.update(block)
        parts.append(block)
    data = b"".join(parts)
    content_hash = hasher.hexdigest()

    # --- 3. Decide the id first, then store the file ---
    document_id = uuid.uuid4()
    storage_key = f"{ctx.org.id}/{document_id.hex}"
    await storage.put(storage_key, data)

    # --- 4. Insert the row now, so a duplicate is caught at this line ---
    document = Document(
        id=document_id,
        organization_id=ctx.org.id,
        uploaded_by=ctx.user.id,
        filename=(file.filename or "untitled")[:255],
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
        content_hash=content_hash,
        status="queued",
    )
    db.add(document)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        await storage.delete(storage_key)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This document has already been uploaded",
        ) from None

    # --- 5. Extract text and build chunks; a failure marks the document failed ---
    try:
        text = extract_text(data, content_type)
        chunk_texts = chunk_text(text)
    except (ExtractionError, ValueError) as e:
        document.status = "failed"
        document.error = str(e)[:500]
    else:
        for idx, chunk_content in enumerate(chunk_texts):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    organization_id=ctx.org.id,
                    chunk_index=idx,
                    text=chunk_content,
                )
            )
        document.status = "ready"

    # --- 6. One commit saves everything together ---
    try:
        await db.commit()
    except Exception:
        await storage.delete(storage_key)
        raise
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: TenantDb) -> list[Document]:
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    db: TenantDb,
) -> Document:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_document_chunks(
    document_id: uuid.UUID,
    db: TenantDb,
) -> list[ChunkOut]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return [
        ChunkOut(chunk_index=chunk.chunk_index, text=chunk.text) for chunk in result.scalars().all()
    ]
