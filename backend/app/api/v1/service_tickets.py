"""Enterprise-service ticket workflow."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.investment import investment_db
from app.core.permissions import require_any_role
from app.core.security import UserContext
from app.database.models.operations import ServiceTicket


router = APIRouter()
WRITE_ROLES = ("super_admin", "park_manager", "enterprise_service")
TicketStatus = Literal["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"]
TicketPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]


class TicketCreate(BaseModel):
    enterprise_id: str | None = Field(default=None, max_length=200)
    enterprise_name: str | None = Field(default=None, max_length=500)
    subject: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=2, max_length=10000)
    category: str = Field(default="综合服务", min_length=1, max_length=100)
    priority: TicketPriority = "MEDIUM"
    assignee_id: str | None = Field(default=None, max_length=50)
    due_at: datetime | None = None
    source_task_id: str | None = Field(default=None, max_length=50)


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: str | None = Field(default=None, max_length=50)
    due_at: datetime | None = None
    resolution: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def require_resolution_when_closed(self):
        if self.status in {"RESOLVED", "CLOSED"} and not (self.resolution or "").strip():
            raise ValueError("办结工单必须填写处理结果")
        return self


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str | None
    enterprise_name: str | None
    subject: str
    description: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    assignee_id: str | None
    due_at: datetime | None
    resolution: str | None
    source_task_id: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@router.get("/service-tickets")
async def list_service_tickets(
    status: TicketStatus | None = None,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=500),
    session: AsyncSession = Depends(investment_db),
    _user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    statement = select(ServiceTicket)
    if status:
        statement = statement.where(ServiceTicket.status == status)
    if q and q.strip():
        token = f"%{q.strip()}%"
        statement = statement.where(or_(
            ServiceTicket.subject.ilike(token),
            ServiceTicket.enterprise_name.ilike(token),
            ServiceTicket.description.ilike(token),
        ))
    items = list((await session.execute(
        statement.order_by(ServiceTicket.updated_at.desc()).limit(limit)
    )).scalars().all())
    return {"success": True, "data": [TicketRead.model_validate(item).model_dump(mode="json") for item in items]}


@router.post("/service-tickets", status_code=201)
async def create_service_ticket(
    body: TicketCreate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    ticket = ServiceTicket(**body.model_dump(), created_by=user.user_id, updated_by=user.user_id)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return {"success": True, "data": TicketRead.model_validate(ticket).model_dump(mode="json")}


@router.patch("/service-tickets/{ticket_id}")
async def update_service_ticket(
    ticket_id: str,
    body: TicketUpdate,
    session: AsyncSession = Depends(investment_db),
    user: UserContext = Depends(require_any_role(*WRITE_ROLES)),
):
    ticket = await session.get(ServiceTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    ticket.updated_by = user.user_id
    ticket.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(ticket)
    return {"success": True, "data": TicketRead.model_validate(ticket).model_dump(mode="json")}
