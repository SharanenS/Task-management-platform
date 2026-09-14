"""Operational metrics endpoint for Prometheus scraping."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics(session: AsyncSession = Depends(get_db)) -> Response:
    """Return operational metrics in standard Prometheus exposition format."""
    text_content = await metrics.generate_prometheus_text(session=session)
    return Response(
        content=text_content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
