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
    # ---1.Validate declared content type and size---
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported file type: {file.content_type}"
        )

    # ---2.Read the file in chunks and compute the hash---
    hasher = hashlib.sha256()
    size_bytes = 0
    while chunk := await file.read(CHUNK_SIZE):
        size_bytes += len(chunk)
        if size_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            )
        hasher.update(chunk)

    content_hash = hasher.hexdigest()

    # ---3 Rewind and read all bytes(storage.put wants bytes)---
    await file.seek(0)
    data = await file.read()

    # ---4. Generate a unique storage key for the file---
    storage_key = f"{ctx.org.id}/{uuid.uuid4().hex}"

    # ---5. Save the file to storage so the db failure can be rolled back---
    await storage.put(storage_key, data)

    # ---6 Create a new Document record in the database
    try:
        document = Document(
            organization_id=ctx.org.id,
            uploaded_by=ctx.user.id,
            filename=file.filename or "untitled",
            storage_key=storage_key,
            content_type=file.content_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            status="queued",
        )

        db.add(document)

    except IntegrityError:
        await db.rollback()
        await storage.delete(storage_key)  # Clean up the stored file
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This document has already been uploaded",
        ) from None

    try:
        text = extract_text(data, file.content_type)
        chunks = chunk_text(text)
        for idx, chunk_content in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    organization_id=ctx.org.id,
                    chunk_index=idx,
                    text=chunk_content,
                )
            )

        document.status = "ready"
        await db.commit()
    except (ExtractionError, ValueError) as e:
        await db.rollback()
        document.status = "failed"
        document.error = str(e)[:500]
        await db.commit()

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
