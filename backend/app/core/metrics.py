"""Operational metrics collection and Prometheus text exposition."""

import threading
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JobStatus, OutboxStatus
from app.models.job import Job
from app.models.outbox import OutboxEvent


class MetricsRegistry:
    """Thread-safe in-memory registry for counters, gauges, and histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Cumulative counters: name -> labels_tuple -> count
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(
            lambda: defaultdict(float)
        )
        # Latency histograms / buckets: name -> bucket_def
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], dict[str, Any]]] = defaultdict(
            lambda: defaultdict(lambda: {"count": 0, "sum": 0.0, "buckets": defaultdict(int)})
        )
        self._default_latency_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a cumulative counter by value."""
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._counters[name][label_key] += value

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: list[float] | None = None,
    ) -> None:
        """Observe a value in a histogram."""
        label_key = tuple(sorted(labels.items())) if labels else ()
        b_list = buckets or self._default_latency_buckets
        with self._lock:
            data = self._histograms[name][label_key]
            data["count"] += 1
            data["sum"] += value
            for b in b_list:
                if value <= b:
                    data["buckets"][b] += 1

    def record_job_execution(
        self,
        job_type: str,
        outcome: str,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        """Record completed or failed job execution with bounded labels."""
        clean_type = job_type or "UNKNOWN"
        self.increment_counter("job_executions_total", 1.0, {"job_type": clean_type, "outcome": outcome})
        self.observe_histogram("job_execution_duration_seconds", duration_seconds, {"job_type": clean_type})
        if outcome == "failure" and error_type:
            clean_err = error_type.replace("\"", "").replace("\n", "")[:50]
            self.increment_counter(
                "job_execution_failures_total", 1.0, {"job_type": clean_type, "error_type": clean_err}
            )

    def record_job_recovery(self, count: int = 1) -> None:
        """Record count of expired jobs reclaimed by recovery daemon."""
        if count > 0:
            self.increment_counter("jobs_recovered_total", float(count))

    def record_outbox_published(self, duration_seconds: float) -> None:
        """Record successfully dispatched outbox event."""
        self.increment_counter("outbox_published_total", 1.0)
        self.observe_histogram("outbox_publish_duration_seconds", duration_seconds)

    def record_outbox_failure(self) -> None:
        """Record failed outbox event dispatch."""
        self.increment_counter("outbox_failures_total", 1.0)

    def record_http_request(self, method: str, status: int, duration_seconds: float) -> None:
        """Record HTTP request duration and status."""
        labels = {"method": method.upper(), "status": str(status)}
        self.increment_counter("http_requests_total", 1.0, labels)
        self.observe_histogram("http_request_duration_seconds", duration_seconds, labels)

    async def collect_database_gauges(self, session: AsyncSession) -> dict[str, list[tuple[dict[str, str], float]]]:
        """
        Query authoritative PostgreSQL counts for durable gauges.
        Returns gauge values grouped by bounded labels.
        """
        gauges: dict[str, list[tuple[dict[str, str], float]]] = {
            "jobs_queued": [],
            "jobs_processing": [],
            "jobs_completed": [],
            "jobs_failed": [],
            "jobs_expired": [({}, 0.0)],
            "outbox_pending": [({}, 0.0)],
            "outbox_failures": [({}, 0.0)],
        }

        try:
            # 1. Job counts by job_type and status
            job_stmt = (
                select(Job.job_type, Job.status, func.count(Job.id))
                .group_by(Job.job_type, Job.status)
            )
            job_rows = (await session.execute(job_stmt)).all()
            for jtype, jstatus, count in job_rows:
                metric_name = f"jobs_{str(jstatus).lower()}"
                if metric_name in gauges:
                    gauges[metric_name].append(({"job_type": str(jtype)}, float(count)))

            # 2. Expired jobs (PROCESSING with past lease)
            expired_stmt = select(func.count(Job.id)).where(
                Job.status == JobStatus.PROCESSING,
                Job.execution_lease_until.is_not(None),
                Job.execution_lease_until < func.now(),
            )
            expired_count = (await session.execute(expired_stmt)).scalar() or 0
            gauges["jobs_expired"] = [({}, float(expired_count))]

            # 3. Outbox pending events
            outbox_pending_stmt = select(func.count(OutboxEvent.id)).where(
                OutboxEvent.status == OutboxStatus.PENDING
            )
            pending_count = (await session.execute(outbox_pending_stmt)).scalar() or 0
            gauges["outbox_pending"] = [({}, float(pending_count))]

            # 4. Outbox failure events (events with attempt_count > 0 or last_error)
            outbox_fail_stmt = select(func.count(OutboxEvent.id)).where(
                OutboxEvent.last_error.is_not(None)
            )
            fail_count = (await session.execute(outbox_fail_stmt)).scalar() or 0
            gauges["outbox_failures"] = [({}, float(fail_count))]

        except Exception:
            # If database query fails, return empty gauges rather than crashing scrape
            pass

        return gauges

    def _escape_label_value(self, v: str) -> str:
        """Escape label value for Prometheus text exposition 0.0.4."""
        return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _format_labels(self, labels: dict[str, str]) -> str:
        """Format label dictionary into Prometheus label string."""
        if not labels:
            return ""
        items = [f'{k}="{self._escape_label_value(v)}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"

    async def generate_prometheus_text(self, session: AsyncSession | None = None) -> str:
        """Render all metrics into standard Prometheus exposition format."""
        lines: list[str] = []

        # Description catalog
        help_strings = {
            "jobs_queued": "Current number of queued jobs in PostgreSQL",
            "jobs_processing": "Current number of actively processing jobs in PostgreSQL",
            "jobs_completed": "Total number of completed jobs in PostgreSQL",
            "jobs_failed": "Total number of failed jobs in PostgreSQL",
            "jobs_expired": "Current number of processing jobs whose execution lease has expired",
            "jobs_recovered_total": "Cumulative count of expired jobs reclaimed by recovery daemon",
            "job_executions_total": "Cumulative count of worker job executions",
            "job_execution_failures_total": "Cumulative count of worker job execution failures",
            "job_execution_duration_seconds": "Duration of job execution handler in seconds",
            "outbox_pending": "Current number of outbox events awaiting publication",
            "outbox_failures": "Current number of outbox events that encountered publication errors",
            "outbox_published_total": "Cumulative count of outbox events published to message broker",
            "outbox_failures_total": "Cumulative count of outbox event publication failures",
            "outbox_publish_duration_seconds": "Duration of outbox event dispatch in seconds",
            "http_requests_total": "Cumulative count of HTTP requests",
            "http_request_duration_seconds": "Duration of HTTP request processing in seconds",
        }

        # 1. Collect DB gauges if session is provided
        if session is not None:
            db_gauges = await self.collect_database_gauges(session)
            for g_name, samples in db_gauges.items():
                if g_name in help_strings:
                    lines.append(f"# HELP {g_name} {help_strings[g_name]}")
                    lines.append(f"# TYPE {g_name} gauge")
                if not samples:
                    lines.append(f"{g_name} 0")
                else:
                    for labels, val in samples:
                        lbl_str = self._format_labels(labels)
                        lines.append(f"{g_name}{lbl_str} {int(val) if val.is_integer() else val}")

        # 2. Render In-Memory Counters
        with self._lock:
            for c_name, series_map in sorted(self._counters.items()):
                if c_name in help_strings:
                    lines.append(f"# HELP {c_name} {help_strings[c_name]}")
                    lines.append(f"# TYPE {c_name} counter")
                for lbl_tuple, val in sorted(series_map.items()):
                    lbl_dict = dict(lbl_tuple)
                    lbl_str = self._format_labels(lbl_dict)
                    lines.append(f"{c_name}{lbl_str} {int(val) if val.is_integer() else val}")

            # 3. Render Histograms
            for h_name, series_map in sorted(self._histograms.items()):
                if h_name in help_strings:
                    lines.append(f"# HELP {h_name} {help_strings[h_name]}")
                    lines.append(f"# TYPE {h_name} histogram")
                for lbl_tuple, data in sorted(series_map.items()):
                    lbl_dict = dict(lbl_tuple)
                    cumulative = 0
                    for b in sorted(data["buckets"].keys()):
                        cumulative += data["buckets"][b]
                        b_labels = dict(lbl_dict)
                        b_labels["le"] = str(b)
                        lines.append(f"{h_name}_bucket{self._format_labels(b_labels)} {cumulative}")
                    inf_labels = dict(lbl_dict)
                    inf_labels["le"] = "+Inf"
                    lines.append(f"{h_name}_bucket{self._format_labels(inf_labels)} {data['count']}")
                    lines.append(f"{h_name}_sum{self._format_labels(lbl_dict)} {data['sum']:.4f}")
                    lines.append(f"{h_name}_count{self._format_labels(lbl_dict)} {data['count']}")

        return "\n".join(lines) + "\n"


# Global singleton instance
metrics = MetricsRegistry()
