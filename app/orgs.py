import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Membership, Organization, User
from app.permissions import OrgMember, OrgOwner

router = APIRouter(prefix="/orgs", tags=["organizations"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class OrgCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrgOut)
async def create_org(body: OrgCreate, user: CurrentUser, db: DbSession) -> OrgOut:
    org = Organization(name=body.name)
    db.add(org)
    await db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
    await db.commit()
    return OrgOut(id=org.id, name=org.name, role="owner")


@router.get("", response_model=list[OrgOut])
async def list_my_orgs(user: CurrentUser, db: DbSession) -> list[OrgOut]:
    result = await db.execute(
        select(Organization.id, Organization.name, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return [OrgOut(id=r.id, name=r.name, role=r.role) for r in result]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str


class MemberAdd(BaseModel):
    email: EmailStr
    role: Literal["owner", "member"] = "member"


@router.get("/{org_id}", response_model=OrgOut)
async def get_org(ctx: OrgMember) -> OrgOut:
    return OrgOut(id=ctx.org.id, name=ctx.org.name, role=ctx.role)


@router.get("/{org_id}/members", response_model=list[MemberOut])
async def list_members(ctx: OrgMember, db: DbSession) -> list[MemberOut]:
    result = await db.execute(
        select(User.id, User.email, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == ctx.org.id)
        .order_by(Membership.created_at)
    )
    return [MemberOut(user_id=r.id, email=r.email, role=r.role) for r in result]


@router.post(
    "/{org_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=MemberOut,
)
async def add_member(body: MemberAdd, ctx: OrgOwner, db: DbSession) -> MemberOut:
    new_user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if new_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    db.add(Membership(user_id=new_user.id, organization_id=ctx.org.id, role=body.role))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member") from None
    return MemberOut(user_id=new_user.id, email=new_user.email, role=body.role)
