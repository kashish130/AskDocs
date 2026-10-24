import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Membership, Organization, User


@dataclass
class OrgContext:
    org: Organization
    user: User
    role: str


async def get_org_context(
    org_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgContext:
    result = await db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Organization.id == org_id, Membership.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    org, role = row
    return OrgContext(org=org, user=user, role=role)


async def require_owner(
    ctx: Annotated[OrgContext, Depends(get_org_context)],
) -> OrgContext:
    if ctx.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner role required")
    return ctx


OrgMember = Annotated[OrgContext, Depends(get_org_context)]
OrgOwner = Annotated[OrgContext, Depends(require_owner)]
