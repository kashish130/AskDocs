from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import router as auth_router
from app.db import get_db
from app.documents import router as documents_router
from app.orgs import router as orgs_router

app = FastAPI()


@app.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}


app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(documents_router)
