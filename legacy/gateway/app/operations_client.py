import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx

from app.config import settings
from app.observability import get_tracing_headers


@dataclass(frozen=True)
class DependencyHealth:
    name: str
    status: str  # "HEALTHY" | "DEGRADED" | "UNAVAILABLE"
    latency_ms: float | None
    message: str | None


@dataclass(frozen=True)
class ServiceHealth:
    service_name: str
    status: str  # "HEALTHY" | "DEGRADED" | "UNAVAILABLE"
    version: str | None
    uptime_seconds: float | None
    checked_at: str
    dependencies: list[DependencyHealth]


@dataclass(frozen=True)
class QueueObservation:
    queue_name: str
    messages_ready: int | None
    messages_unacknowledged: int | None
    consumers_count: int | None
    measured_at: str


@dataclass(frozen=True)
class JobOperations:
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    exhausted_count: int
    oldest_pending_age_seconds: float | None
    recent_failures_count: int
    measured_at: str


@dataclass(frozen=True)
class TelemetryLink:
    name: str
    url: str
    description: str


@dataclass(frozen=True)
class OperationsSummaryData:
    generated_at: str
    overall_status: str
    services: list[ServiceHealth]
    job_operations: JobOperations
    queues: list[QueueObservation]
    telemetry_tools: list[TelemetryLink]


GATEWAY_START_TIME = time.time()


async def _check_endpoint(
    name: str,
    ready_url: str,
    db_name: str = "PostgreSQL",
    extra_headers: dict[str, str] | None = None,
) -> ServiceHealth:
    now = datetime.now(UTC).isoformat()
    req_headers = {**get_tracing_headers(), **(extra_headers or {})}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(ready_url, headers=req_headers)
            latency = round((time.monotonic() - started) * 1000, 2)
            if resp.status_code == 200:
                return ServiceHealth(
                    service_name=name,
                    status="HEALTHY",
                    version="0.1.0",
                    uptime_seconds=None,
                    checked_at=now,
                    dependencies=[
                        DependencyHealth(
                            name=db_name,
                            status="HEALTHY",
                            latency_ms=latency,
                            message=None,
                        )
                    ],
                )
            return ServiceHealth(
                service_name=name,
                status="DEGRADED",
                version="0.1.0",
                uptime_seconds=None,
                checked_at=now,
                dependencies=[
                    DependencyHealth(
                        name=db_name,
                        status="DEGRADED",
                        latency_ms=latency,
                        message=f"HTTP {resp.status_code}",
                    )
                ],
            )
    except Exception as exc:
        latency = round((time.monotonic() - started) * 1000, 2)
        return ServiceHealth(
            service_name=name,
            status="UNAVAILABLE",
            version=None,
            uptime_seconds=None,
            checked_at=now,
            dependencies=[
                DependencyHealth(
                    name=db_name,
                    status="UNAVAILABLE",
                    latency_ms=latency,
                    message=exc.__class__.__name__,
                )
            ],
        )


async def _check_keycloak() -> DependencyHealth:
    started = time.monotonic()
    try:
        certs_url = settings.oidc_jwks_url
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(certs_url)
            latency = round((time.monotonic() - started) * 1000, 2)
            if resp.status_code == 200:
                return DependencyHealth(
                    name="Keycloak OIDC",
                    status="HEALTHY",
                    latency_ms=latency,
                    message=None,
                )
            return DependencyHealth(
                name="Keycloak OIDC",
                status="DEGRADED",
                latency_ms=latency,
                message=f"HTTP {resp.status_code}",
            )
    except Exception as exc:
        latency = round((time.monotonic() - started) * 1000, 2)
        return DependencyHealth(
            name="Keycloak OIDC",
            status="UNAVAILABLE",
            latency_ms=latency,
            message=exc.__class__.__name__,
        )


async def _fetch_job_operations() -> tuple[JobOperations, list[QueueObservation]]:
    now = datetime.now(UTC).isoformat()
    default_job_ops = JobOperations(
        pending_count=0,
        running_count=0,
        completed_count=0,
        failed_count=0,
        cancelled_count=0,
        exhausted_count=0,
        oldest_pending_age_seconds=None,
        recent_failures_count=0,
        measured_at=now,
    )
    default_queues: list[QueueObservation] = [
        QueueObservation("job.execution", None, None, None, now),
        QueueObservation("celery", None, None, None, now),
    ]

    try:
        url = f"{settings.job_service_url}/internal/operations/summary"
        headers = {
            "X-Internal-Service-Key": settings.job_internal_service_key,
            **get_tracing_headers(),
        }
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                job_ops = JobOperations(
                    pending_count=data.get("pending_count", 0),
                    running_count=data.get("running_count", 0),
                    completed_count=data.get("completed_count", 0),
                    failed_count=data.get("failed_count", 0),
                    cancelled_count=data.get("cancelled_count", 0),
                    exhausted_count=data.get("exhausted_count", 0),
                    oldest_pending_age_seconds=data.get("oldest_pending_age_seconds"),
                    recent_failures_count=data.get("recent_failures_count", 0),
                    measured_at=data.get("measured_at", now),
                )
                raw_queues = data.get("queues", [])
                queues = [
                    QueueObservation(
                        queue_name=q["queue_name"],
                        messages_ready=q.get("messages_ready"),
                        messages_unacknowledged=q.get("messages_unacknowledged"),
                        consumers_count=q.get("consumers_count"),
                        measured_at=q.get("measured_at", now),
                    )
                    for q in raw_queues
                ]
                return job_ops, queues or default_queues
    except Exception:
        pass
    return default_job_ops, default_queues


async def _fetch_work_outbox_queues() -> list[QueueObservation]:
    now = datetime.now(UTC).isoformat()
    try:
        url = f"{settings.work_service_url}/internal/operations/summary"
        headers = {
            "X-Internal-Service-Key": settings.work_internal_service_key,
            **get_tracing_headers(),
        }
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return [
                    QueueObservation(
                        queue_name="work.outbox.events",
                        messages_ready=data.get("pending_count", 0),
                        messages_unacknowledged=data.get("in_flight_count", 0),
                        consumers_count=1,
                        measured_at=data.get("measured_at", now),
                    )
                ]
    except Exception:
        pass
    return [QueueObservation("work.outbox.events", None, None, None, now)]


async def get_operations_summary() -> OperationsSummaryData:
    now = datetime.now(UTC).isoformat()

    # Parallel health checks
    employee_task = _check_endpoint("employee", f"{settings.employee_service_url}/health/ready")
    work_task = _check_endpoint("work", f"{settings.work_service_url}/health/ready")
    job_task = _check_endpoint("job", f"{settings.job_service_url}/health/ready")
    workflow_task = _check_endpoint("workflow", f"{settings.workflow_service_url}/health/ready")
    notification_task = _check_endpoint(
        "notification", f"{settings.notification_service_url}/health/ready"
    )
    keycloak_task = _check_keycloak()
    job_ops_task = _fetch_job_operations()
    work_outbox_task = _fetch_work_outbox_queues()

    results = await asyncio.gather(
        employee_task,
        work_task,
        job_task,
        workflow_task,
        notification_task,
        keycloak_task,
        job_ops_task,
        work_outbox_task,
    )
    employee_health = cast(ServiceHealth, results[0])
    work_health = cast(ServiceHealth, results[1])
    job_health = cast(ServiceHealth, results[2])
    workflow_health = cast(ServiceHealth, results[3])
    notification_health = cast(ServiceHealth, results[4])
    kc_dep = cast(DependencyHealth, results[5])
    job_ops, job_queues = cast(tuple[JobOperations, list[QueueObservation]], results[6])
    work_queues = cast(list[QueueObservation], results[7])

    # Gateway self-health
    gateway_uptime = round(time.time() - GATEWAY_START_TIME, 2)
    gateway_health = ServiceHealth(
        service_name="gateway",
        status="HEALTHY" if kc_dep.status == "HEALTHY" else "DEGRADED",
        version="0.1.0",
        uptime_seconds=gateway_uptime,
        checked_at=now,
        dependencies=[kc_dep],
    )

    all_services = [
        gateway_health,
        employee_health,
        work_health,
        job_health,
        workflow_health,
        notification_health,
    ]

    all_queues = list(job_queues) + list(work_queues)

    # Determine overall platform status honestly
    statuses = [s.status for s in all_services]
    if statuses.count("UNAVAILABLE") >= 3:
        overall = "UNAVAILABLE"
    elif "UNAVAILABLE" in statuses or "DEGRADED" in statuses:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    telemetry_tools = [
        TelemetryLink(
            name="Grafana Dashboards",
            url="http://127.0.0.1:3001",
            description=(
                "Consolidated dashboards for service requests, latencies, and job executions."
            ),
        ),
        TelemetryLink(
            name="Jaeger Tracing",
            url="http://127.0.0.1:16686",
            description=(
                "Distributed trace timeline and span latency breakdown across gateway and services."
            ),
        ),
        TelemetryLink(
            name="Prometheus Metrics",
            url="http://127.0.0.1:9090",
            description=(
                "Prometheus targets, raw metric inspection, PromQL queries, and alerting status."
            ),
        ),
    ]

    return OperationsSummaryData(
        generated_at=now,
        overall_status=overall,
        services=all_services,
        job_operations=job_ops,
        queues=all_queues,
        telemetry_tools=telemetry_tools,
    )
