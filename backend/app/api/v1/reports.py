"""Report endpoints Ã¢â‚¬â€ async generation via Celery."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserResponse
from app.api.deps import CurrentUser, get_db, require_permission
from app.core.constants import Permission
from app.schemas.report import ReportCreate, ReportResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=202)
async def create_report(
    body: ReportCreate,
    current_user: UserResponse = Depends(require_permission(Permission.REPORTS_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """Request a new report Ã¢â‚¬â€ returns 202 Accepted, generates async."""
    service = ReportService(db)
    return await service.request_report(body, user_id=current_user.id)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    current_user: UserResponse = Depends(require_permission(Permission.REPORTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List reports for the current user."""
    service = ReportService(db)
    return await service.list_user_reports(current_user.id)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    current_user: UserResponse = Depends(require_permission(Permission.REPORTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific report by ID."""
    service = ReportService(db)
    return await service.get_report(report_id)