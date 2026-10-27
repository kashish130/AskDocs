import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Document
from app.permissions import OrgMember
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


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentOut)
async def upload_document(
    ctx: OrgMember,
    file: Annotated[UploadFile, File(...)],
    db: Dbsession,
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
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await storage.delete(storage_key)  # Clean up the stored file
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This document has already been uploaded",
        ) from None

    await db.refresh(document)
    return document
