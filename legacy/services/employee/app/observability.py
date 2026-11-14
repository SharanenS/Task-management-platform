import json
import logging
import os
import re
import sys
import threading
import time
import urllib.request
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# Context variables for request tracking
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id_ctx", default="")
trace_id_ctx: ContextVar[str] = ContextVar("trace_id_ctx", default="")
span_id_ctx: ContextVar[str] = ContextVar("span_id_ctx", default="")

# Validation patterns
CORRELATION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
TRACEPARENT_PATTERN = re.compile(r"^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-([0-9a-fA-F]{2})$")
ZERO_TRACE_ID = "0" * 32
ZERO_SPAN_ID = "0" * 16

# Redaction patterns
SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "key",
    "email",
    "content",
    "body",
    "comment",
    "title",
    "assignee",
    "sql",
)
JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
BEARER_PATTERN = re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def validate_correlation_id(raw_id: str | None) -> str:
    """Validate correlation ID or generate a safe UUIDv4 fallback."""
    if raw_id and isinstance(raw_id, str):
        cleaned = raw_id.strip()
        if CORRELATION_ID_PATTERN.match(cleaned):
            return cleaned
    return str(uuid4())


def parse_traceparent(raw_tp: str | None) -> tuple[str, str, str] | None:
    """Parse W3C traceparent header: 00-{trace_id}-{span_id}-{flags}."""
    if not raw_tp or not isinstance(raw_tp, str):
        return None
    match = TRACEPARENT_PATTERN.match(raw_tp.strip())
    if not match:
        return None
    trace_id, parent_span_id, flags = match.groups()
    if trace_id == ZERO_TRACE_ID or parent_span_id == ZERO_SPAN_ID:
        return None
    return trace_id.lower(), parent_span_id.lower(), flags.lower()


def format_traceparent(trace_id: str, span_id: str, flags: str = "01") -> str:
    """Format W3C traceparent header."""
    return f"00-{trace_id}-{span_id}-{flags}"


def get_correlation_id() -> str:
    return correlation_id_ctx.get() or ""


def get_traceparent() -> str:
    tid = trace_id_ctx.get()
    sid = span_id_ctx.get()
    if tid and sid:
        return format_traceparent(tid, sid)
    return ""


def get_tracing_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    cid = get_correlation_id()
    if cid:
        headers["X-Correlation-ID"] = cid
    tp = get_traceparent()
    if tp:
        headers["traceparent"] = tp
    return headers


def generate_trace_id() -> str:
    """Generate 16-byte random hex string for OpenTelemetry trace ID."""
    return uuid4().hex


def generate_span_id() -> str:
    """Generate 8-byte random hex string for OpenTelemetry span ID."""
    return uuid4().hex[:16]


def sanitize_data(data: Any, key_name: str = "") -> Any:
    """Recursively scrub sensitive keys and patterns from log records and attributes."""
    if key_name and any(sub in key_name.lower() for sub in SENSITIVE_KEY_SUBSTRINGS):
        return "[REDACTED]"

    if isinstance(data, dict):
        return {str(k): sanitize_data(v, str(k)) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [sanitize_data(item, key_name) for item in data]
    if isinstance(data, str):
        scrubbed = JWT_PATTERN.sub("[REDACTED_JWT]", data)
        scrubbed = BEARER_PATTERN.sub("Bearer [REDACTED]", scrubbed)
        scrubbed = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", scrubbed)
        return scrubbed
    return data


class StructuredLogger:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self._logger = logging.getLogger(service_name)

    def log(
        self,
        level: str,
        event: str,
        outcome: str = "unknown",
        error_code: str | None = None,
        **kwargs: Any,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level.upper(),
            "service": self.service_name,
            "event": event,
            "correlation_id": correlation_id_ctx.get() or "unknown",
            "trace_id": trace_id_ctx.get() or "unknown",
            "span_id": span_id_ctx.get() or "unknown",
            "outcome": outcome,
        }
        if error_code:
            record["error_code"] = str(error_code)

        sanitized_kwargs = sanitize_data(kwargs)
        if isinstance(sanitized_kwargs, dict):
            record.update(sanitized_kwargs)

        message = json.dumps(record, default=str)
        lvl = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(lvl, message)

    def info(self, event: str, outcome: str = "success", **kwargs: Any) -> None:
        self.log("INFO", event, outcome=outcome, **kwargs)

    def warning(self, event: str, outcome: str = "failure", **kwargs: Any) -> None:
        self.log("WARNING", event, outcome=outcome, **kwargs)

    def error(self, event: str, outcome: str = "failure", **kwargs: Any) -> None:
        self.log("ERROR", event, outcome=outcome, **kwargs)


class Span:
    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None = None,
        links: list[dict[str, str]] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.links = links or []
        self.attributes = sanitize_data(attributes or {})
        self.start_time_ns = time.time_ns()
        self.end_time_ns: int | None = None
        self.status = "OK"
        self._token_span: Any = None
        self._token_trace: Any = None

    def set_attribute(self, key: str, value: Any) -> None:
        if isinstance(self.attributes, dict):
            self.attributes[key] = sanitize_data(value, key)

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time_ns = time.time_ns()
        if self._token_span:
            span_id_ctx.reset(self._token_span)
        if self._token_trace:
            trace_id_ctx.reset(self._token_trace)

    def to_otlp_dict(self) -> dict[str, Any]:
        attrs = []
        if isinstance(self.attributes, dict):
            for k, v in self.attributes.items():
                val_dict: dict[str, Any]
                if isinstance(v, bool):
                    val_dict = {"boolValue": v}
                elif isinstance(v, int):
                    val_dict = {"intValue": str(v)}
                elif isinstance(v, float):
                    val_dict = {"doubleValue": v}
                else:
                    val_dict = {"stringValue": str(v)}
                attrs.append({"key": k, "value": val_dict})

        span_data: dict[str, Any] = {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "name": self.name,
            "kind": 1,
            "startTimeUnixNano": str(self.start_time_ns),
            "endTimeUnixNano": str(self.end_time_ns or self.start_time_ns),
            "attributes": attrs,
            "status": {"code": 1 if self.status == "OK" else 2},
        }
        if self.parent_span_id:
            span_data["parentSpanId"] = self.parent_span_id
        if self.links:
            span_data["links"] = [
                {"traceId": link.get("trace_id"), "spanId": link.get("span_id")}
                for link in self.links
                if "trace_id" in link and "span_id" in link
            ]
        return span_data

    def __enter__(self) -> "Span":
        self._token_trace = trace_id_ctx.set(self.trace_id)
        self._token_span = span_id_ctx.set(self.span_id)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.status = "ERROR"
            self.set_attribute("error", True)
            self.set_attribute("error.type", exc_type.__name__)
        self.end()
        telemetry.export_span(self)


class BoundedOTLPTraceExporter:
    def __init__(self, endpoint: str | None = None, service_name: str = "employee") -> None:
        self.endpoint = endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318/v1/traces"
        )
        self.service_name = service_name
        self.queue: list[dict[str, Any]] = []
        self.max_queue_size = 1000
        self.batch_size = 50
        self.lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._pid = os.getpid()
        self.stopped = False
        self._last_error_time = 0.0
        self._worker_thread: threading.Thread | None = None
        self._start_worker()

    def _start_worker(self) -> None:
        self._worker_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._worker_thread.start()

    def _ensure_worker(self) -> None:
        current_pid = os.getpid()
        if (
            self._pid != current_pid
            or self._worker_thread is None
            or not self._worker_thread.is_alive()
        ):
            with self._init_lock:
                if (
                    self._pid != current_pid
                    or self._worker_thread is None
                    or not self._worker_thread.is_alive()
                ):
                    self._pid = current_pid
                    self.lock = threading.Lock()
                    self._worker_thread = threading.Thread(target=self._flush_loop, daemon=True)
                    self._worker_thread.start()

    def export(self, span: Span) -> None:
        if self.stopped:
            return
        self._ensure_worker()
        span_dict = span.to_otlp_dict()
        with self.lock:
            if len(self.queue) < self.max_queue_size:
                self.queue.append(span_dict)

    def flush(self) -> None:
        self._flush_batch()

    def _flush_loop(self) -> None:
        while not self.stopped:
            time.sleep(0.5)
            self._flush_batch()

    def _flush_batch(self) -> None:
        batch: list[dict[str, Any]] = []
        with self.lock:
            if not self.queue:
                return
            batch = self.queue[: self.batch_size]
            self.queue = self.queue[self.batch_size :]

        if not batch or not self.endpoint:
            return

        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}}
                        ]
                    },
                    "scopeSpans": [{"scope": {"name": self.service_name}, "spans": batch}],
                }
            ]
        }
        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.5):
                pass
        except Exception:
            now = time.time()
            if now - self._last_error_time > 60:
                self._last_error_time = now
                sys.stderr.write(
                    f"Telemetry exporter unavailable ({self.endpoint}), dropping spans.\n"
                )

    def shutdown(self, timeout: float = 2.0) -> None:
        self.stopped = True
        self._flush_batch()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)


class TelemetryManager:
    _instance: "TelemetryManager | None" = None

    def __init__(self, service_name: str = "employee") -> None:
        self.service_name = service_name
        self.logger = StructuredLogger(service_name)
        self.exporter = BoundedOTLPTraceExporter(service_name=service_name)

    @classmethod
    def get_instance(cls, service_name: str = "employee") -> "TelemetryManager":
        if cls._instance is None:
            cls._instance = cls(service_name)
        return cls._instance

    def export_span(self, span: Span) -> None:
        self.exporter.export(span)

    def flush(self) -> None:
        self.exporter.flush()

    def start_span(
        self,
        name: str,
        parent_trace_id: str | None = None,
        parent_span_id: str | None = None,
        links: list[dict[str, str]] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        trace_id = parent_trace_id or trace_id_ctx.get() or generate_trace_id()
        parent_id = parent_span_id or span_id_ctx.get() or None
        span_id = generate_span_id()
        return Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            links=links,
            attributes=attributes,
        )


telemetry = TelemetryManager.get_instance("employee")


class PrometheusMetrics:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.lock = threading.Lock()
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}
        self.help_text: dict[str, str] = {}
        self.metric_types: dict[str, str] = {}

    def _normalize_labels(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        clean = {"service": self.service_name}
        for k, v in labels.items():
            clean_k = re.sub(r"[^a-zA-Z0-9_]", "_", str(k))[:32]
            clean_v = re.sub(r"[^a-zA-Z0-9_\-\./]", "_", str(v))[:64]
            clean[clean_k] = clean_v
        return tuple(sorted(clean.items()))

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        norm = self._normalize_labels(labels or {})
        with self.lock:
            key = (name, norm)
            self.counters[key] = self.counters.get(key, 0.0) + value
            if name not in self.help_text:
                self.help_text[name] = help_text or f"Counter metric {name}"
                self.metric_types[name] = "counter"

    def gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None, help_text: str = ""
    ) -> None:
        norm = self._normalize_labels(labels or {})
        with self.lock:
            key = (name, norm)
            self.gauges[key] = value
            if name not in self.help_text:
                self.help_text[name] = help_text or f"Gauge metric {name}"
                self.metric_types[name] = "gauge"

    def histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None, help_text: str = ""
    ) -> None:
        norm = self._normalize_labels(labels or {})
        with self.lock:
            key = (name, norm)
            if key not in self.histograms:
                self.histograms[key] = []
            self.histograms[key].append(value)
            if name not in self.help_text:
                self.help_text[name] = help_text or f"Histogram metric {name}"
                self.metric_types[name] = "histogram"

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self.lock:
            all_names = sorted(set(list(self.metric_types.keys())))
            for name in all_names:
                mtype = self.metric_types[name]
                htext = self.help_text.get(name, "")
                lines.append(f"# HELP {name} {htext}")
                lines.append(f"# TYPE {name} {mtype}")

                if mtype == "counter":
                    for (mname, labels), val in sorted(self.counters.items()):
                        if mname == name:
                            lbl_str = ",".join(f'{k}="{v}"' for k, v in labels)
                            lines.append(f"{mname}{{{lbl_str}}} {val}")
                elif mtype == "gauge":
                    for (mname, labels), val in sorted(self.gauges.items()):
                        if mname == name:
                            lbl_str = ",".join(f'{k}="{v}"' for k, v in labels)
                            lines.append(f"{mname}{{{lbl_str}}} {val}")
                elif mtype == "histogram":
                    buckets = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
                    for (mname, labels), values in sorted(self.histograms.items()):
                        if mname == name:
                            lbl_pairs = list(labels)
                            count = len(values)
                            val_sum = sum(values)
                            for b in buckets:
                                b_count = sum(1 for v in values if v <= b)
                                b_labels = lbl_pairs + [("le", str(b))]
                                lbl_str = ",".join(f'{k}="{v}"' for k, v in b_labels)
                                lines.append(f"{mname}_bucket{{{lbl_str}}} {b_count}")
                            inf_labels = lbl_pairs + [("le", "+Inf")]
                            lbl_str = ",".join(f'{k}="{v}"' for k, v in inf_labels)
                            lines.append(f"{mname}_bucket{{{lbl_str}}} {count}")
                            sum_str = ",".join(f'{k}="{v}"' for k, v in lbl_pairs)
                            lines.append(f"{mname}_sum{{{sum_str}}} {round(val_sum, 4)}")
                            lines.append(f"{mname}_count{{{sum_str}}} {count}")
        return "\n".join(lines) + "\n"


metrics = PrometheusMetrics("employee")
