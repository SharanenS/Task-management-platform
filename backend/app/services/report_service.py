"""Report service — async report generation via Celery."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.report import Report
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportCreate, ReportResponse

logger = get_logger(__name__)


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.report_repo = ReportRepository(session)

    async def request_report(
        self, data: ReportCreate, user_id: uuid.UUID
    ) -> ReportResponse:
        """Create a report request and dispatch to Celery."""
        report = Report(
            project_id=data.project_id,
            requested_by=user_id,
        )
        report = await self.report_repo.create(report)

        # TODO: Dispatch Celery task
        # from app.tasks.report_tasks import generate_report
        # generate_report.delay(str(report.id))

        logger.info("report_requested", report_id=str(report.id))
        return self._to_response(report)

    async def get_report(self, report_id: uuid.UUID) -> ReportResponse:
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(f"Report {report_id} not found")
        return self._to_response(report)

    async def list_user_reports(self, user_id: uuid.UUID) -> list[ReportResponse]:
        reports = await self.report_repo.list_by_user(user_id)
        return [self._to_response(r) for r in reports]

    def _to_response(self, report: Report) -> ReportResponse:
        return ReportResponse(
            id=report.id,
            project_id=report.project_id,
            requested_by=report.requested_by,
            status=report.status,
            file_url=report.file_url,
            error_message=report.error_message,
            created_at=report.created_at,
            completed_at=report.completed_at,
        )