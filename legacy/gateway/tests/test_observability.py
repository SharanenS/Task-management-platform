import json
import logging

import pytest
import strawberry

from app.observability import (
    BoundedOTLPTraceExporter,
    PrometheusMetrics,
    StructuredLogger,
    categorize_graphql_operation,
    correlation_id_ctx,
    format_traceparent,
    parse_traceparent,
    sanitize_data,
    span_id_ctx,
    trace_id_ctx,
    validate_correlation_id,
)


@strawberry.type
class DepthTestTreeNode:
    val: str = "ok"

    @strawberry.field
    def child(self) -> "DepthTestTreeNode | None":
        return DepthTestTreeNode()


@strawberry.type
class DepthTestQuery:
    @strawberry.field
    def tree(self) -> DepthTestTreeNode:
        return DepthTestTreeNode()


def test_validate_correlation_id() -> None:
    # Valid IDs
    assert validate_correlation_id("req-12345_abc") == "req-12345_abc"
    assert validate_correlation_id("a" * 64) == "a" * 64

    # Invalid characters / CRLF log injection attempts
    assert validate_correlation_id("req\nINJECTION: true") != "req\nINJECTION: true"
    assert len(validate_correlation_id("req\nINJECTION: true")) == 36  # UUID length
    assert validate_correlation_id("bad;drop table") != "bad;drop table"
    assert validate_correlation_id("<script>") != "<script>"

    # None and empty
    assert len(validate_correlation_id(None)) == 36
    assert len(validate_correlation_id("")) == 36

    # Length > 64
    assert len(validate_correlation_id("a" * 65)) == 36


def test_parse_and_format_traceparent() -> None:
    valid_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    parsed = parse_traceparent(valid_tp)
    assert parsed is not None
    trace_id, span_id, flags = parsed
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_id == "00f067aa0ba902b7"
    assert flags == "01"

    formatted = format_traceparent(trace_id, span_id, flags)
    assert formatted == valid_tp

    # Invalid version or length
    assert parse_traceparent("01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01") is None
    assert parse_traceparent("00-too-short-span-01") is None

    # All zeros is forbidden by W3C specification
    all_zero_trace = "00-00000000000000000000000000000000-00f067aa0ba902b7-01"
    assert parse_traceparent(all_zero_trace) is None
    all_zero_span = "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01"
    assert parse_traceparent(all_zero_span) is None


def test_sanitize_data_redaction() -> None:
    raw = {
        "user_id": "123",
        "password": "supersecretpassword",
        "api_token": "secret_abc",
        "authorization_header": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
        "email_address": "user@example.test",
        "task_title": "Fix critical bug in billing",
        "nested": {
            "internal_key": "secret-service-key",
            "comment_body": "This is sensitive comment text",
        },
        "log_message": "User admin@example.com logged in with token eyJ123.456.789",
    }

    sanitized = sanitize_data(raw)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_token"] == "[REDACTED]"
    assert sanitized["authorization_header"] == "[REDACTED]"
    assert sanitized["email_address"] == "[REDACTED]"
    assert sanitized["task_title"] == "[REDACTED]"
    assert sanitized["nested"]["internal_key"] == "[REDACTED]"
    assert sanitized["nested"]["comment_body"] == "[REDACTED]"

    # Pattern redactions inside arbitrary strings
    assert "admin@example.com" not in sanitized["log_message"]
    assert "[REDACTED_EMAIL]" in sanitized["log_message"]
    assert "eyJ123.456.789" not in sanitized["log_message"]
    assert "[REDACTED_JWT]" in sanitized["log_message"]


def test_structured_logger(caplog: pytest.LogCaptureFixture) -> None:
    logger = StructuredLogger("test-service")
    c_token = correlation_id_ctx.set("corr-xyz-123")
    t_token = trace_id_ctx.set("trace-abc")
    s_token = span_id_ctx.set("span-def")

    try:
        with caplog.at_level(logging.INFO):
            logger.info("user_login", outcome="success", client_ip="127.0.0.1", password="secret")

        assert len(caplog.records) == 1
        data = json.loads(caplog.records[0].message)
        assert data["service"] == "test-service"
        assert data["event"] == "user_login"
        assert data["outcome"] == "success"
        assert data["correlation_id"] == "corr-xyz-123"
        assert data["trace_id"] == "trace-abc"
        assert data["span_id"] == "span-def"
        assert data["client_ip"] == "127.0.0.1"
        assert data["password"] == "[REDACTED]"
    finally:
        correlation_id_ctx.reset(c_token)
        trace_id_ctx.reset(t_token)
        span_id_ctx.reset(s_token)


def test_prometheus_metrics_and_cardinality() -> None:
    prom = PrometheusMetrics("test-svc")
    prom.counter(
        "http_requests_total", 1, {"method": "GET", "status": "200"}, "Total HTTP requests"
    )
    prom.counter("http_requests_total", 2, {"method": "GET", "status": "200"})
    prom.counter("http_requests_total", 1, {"method": "POST", "status": "500"})
    prom.gauge("dependency_up", 1.0, {"dependency": "database"}, "Database health")
    prom.histogram("http_request_duration_seconds", 0.04, {"method": "GET"}, "Request duration")

    rendered = prom.render_prometheus()
    assert "# HELP http_requests_total Total HTTP requests" in rendered
    assert "# TYPE http_requests_total counter" in rendered
    assert 'http_requests_total{method="GET",service="test-svc",status="200"} 3.0' in rendered
    assert 'http_requests_total{method="POST",service="test-svc",status="500"} 1.0' in rendered
    assert "# TYPE dependency_up gauge" in rendered
    assert 'dependency_up{dependency="database",service="test-svc"} 1.0' in rendered
    assert (
        'http_request_duration_seconds_bucket{method="GET",service="test-svc",le="0.05"} 1'
        in rendered
    )
    assert 'http_request_duration_seconds_count{method="GET",service="test-svc"} 1' in rendered

    # Cardinality normalization (truncates long labels and removes invalid characters)
    prom.counter("events_total", 1, {"unbounded_id": "a" * 100, "bad:key!": "value"})
    rendered_norm = prom.render_prometheus()
    assert len("a" * 100) > 64
    assert ("a" * 64) in rendered_norm


def test_graphql_operation_categorization() -> None:
    # Queries
    assert categorize_graphql_operation("query Dashboard { dashboard { workAvailable } }") == (
        "query",
        "query_dashboard",
    )
    assert categorize_graphql_operation(
        "query Ops { operationsSummary { services { name } } }"
    ) == (
        "query",
        "query_operations",
    )
    assert categorize_graphql_operation(
        "query GetProjects { projects(first: 10) { items { id } } }"
    ) == (
        "query",
        "query_projects",
    )
    assert categorize_graphql_operation("query MyWorkflows { workflows { id } }") == (
        "query",
        "query_workflows",
    )

    # Mutations
    assert categorize_graphql_operation("mutation CreateTask { createTask(input: {}) { id } }") == (
        "mutation",
        "mutation_create_task",
    )
    assert categorize_graphql_operation('mutation Assign { assignTask(taskId: "1") { id } }') == (
        "mutation",
        "mutation_assign_task",
    )

    # Unknown or arbitrary queries map to bounded 'other'
    assert categorize_graphql_operation("query { arbitrarySecretField }") == ("query", "other")
    assert categorize_graphql_operation(None) == ("unknown", "invalid")


def test_bounded_trace_exporter_resilience() -> None:
    # Exporter should never throw even if target endpoint is completely invalid or down
    exporter = BoundedOTLPTraceExporter(
        endpoint="http://127.0.0.1:59999/unreachable", service_name="test"
    )
    try:
        from app.observability import Span

        span = Span(name="test_span", trace_id="1" * 32, span_id="2" * 16)
        span.end()
        exporter.export(span)

        # Force a flush batch
        exporter._flush_batch()
    finally:
        exporter.shutdown(timeout=0.5)


def test_operations_summary_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import Identity
    from app.employee_client import EmployeeProfile
    from app.main import app

    def send_graphql(headers: dict[str, str] | None = None) -> dict:
        import asyncio

        import httpx

        async def _call():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                return await client.post(
                    "/graphql",
                    json={
                        "query": """
                        query GetOps {
                            operationsSummary {
                                overallStatus
                                services {
                                    serviceName
                                    status
                                }
                                telemetryTools {
                                    name
                                    url
                                }
                            }
                        }
                        """
                    },
                    headers=headers,
                )

        resp = asyncio.run(_call())
        return resp.json()

    # 1. Unauthenticated -> UNAUTHENTICATED
    res_unauth = send_graphql()
    assert res_unauth["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"

    # Mock token validation
    monkeypatch.setattr(
        "app.schema.token_validator.validate",
        lambda _: Identity(subject="sub-123"),
    )

    # 2. Role MEMBER -> FORBIDDEN
    async def mock_get_member(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="11111111-1111-4111-8111-111111111111",
            display_name="Member",
            email="member@test.org",
            role="MEMBER",
        )

    monkeypatch.setattr("app.schema.get_employee", mock_get_member)
    res_member = send_graphql(headers={"Authorization": "Bearer member-token"})
    assert res_member["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # 3. Role MANAGER -> FORBIDDEN
    async def mock_get_manager(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="22222222-2222-4222-8222-222222222222",
            display_name="Manager",
            email="manager@test.org",
            role="MANAGER",
        )

    monkeypatch.setattr("app.schema.get_employee", mock_get_manager)
    res_mgr = send_graphql(headers={"Authorization": "Bearer manager-token"})
    assert res_mgr["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # 4. Inactive/Deactivated profile -> FORBIDDEN
    from app.employee_client import EmployeeForbiddenError, EmployeeUnavailableError

    async def mock_get_forbidden(_: str) -> EmployeeProfile:
        raise EmployeeForbiddenError()

    monkeypatch.setattr("app.schema.get_employee", mock_get_forbidden)
    res_inactive = send_graphql(headers={"Authorization": "Bearer inactive-token"})
    assert res_inactive["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # 5. Missing profile (404 mapped to EmployeeForbiddenError) -> FORBIDDEN
    res_missing = send_graphql(headers={"Authorization": "Bearer missing-profile-token"})
    assert res_missing["errors"][0]["extensions"]["code"] == "FORBIDDEN"

    # 6. Employee service unavailable -> SERVICE_UNAVAILABLE
    async def mock_get_unavailable(_: str) -> EmployeeProfile:
        raise EmployeeUnavailableError()

    monkeypatch.setattr("app.schema.get_employee", mock_get_unavailable)
    res_unavail = send_graphql(headers={"Authorization": "Bearer token"})
    assert res_unavail["errors"][0]["extensions"]["code"] == "SERVICE_UNAVAILABLE"

    # 7. Role ADMIN -> Success
    async def mock_get_admin(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="33333333-3333-4333-8333-333333333333",
            display_name="Admin",
            email="admin@test.org",
            role="ADMIN",
        )

    monkeypatch.setattr("app.schema.get_employee", mock_get_admin)

    from app.operations_client import (
        DependencyHealth,
        JobOperations,
        OperationsSummaryData,
        QueueObservation,
        ServiceHealth,
        TelemetryLink,
    )

    async def mock_operations_summary() -> OperationsSummaryData:
        return OperationsSummaryData(
            generated_at="2026-11-07T00:00:00Z",
            overall_status="HEALTHY",
            services=[
                ServiceHealth(
                    service_name="gateway",
                    status="HEALTHY",
                    version="0.1.0",
                    uptime_seconds=120.0,
                    checked_at="2026-11-07T00:00:00Z",
                    dependencies=[
                        DependencyHealth(
                            name="Keycloak OIDC",
                            status="HEALTHY",
                            latency_ms=4.2,
                            message=None,
                        )
                    ],
                )
            ],
            job_operations=JobOperations(
                pending_count=0,
                running_count=0,
                completed_count=10,
                failed_count=0,
                cancelled_count=0,
                exhausted_count=0,
                oldest_pending_age_seconds=None,
                recent_failures_count=0,
                measured_at="2026-11-07T00:00:00Z",
            ),
            queues=[QueueObservation("job.execution", 0, 0, 1, "2026-11-07T00:00:00Z")],
            telemetry_tools=[
                TelemetryLink(
                    name="Grafana",
                    url="http://127.0.0.1:3001",
                    description="Dashboards",
                )
            ],
        )

    monkeypatch.setattr("app.schema.get_operations_summary", mock_operations_summary)
    res_admin = send_graphql(headers={"Authorization": "Bearer admin-token"})
    assert "errors" not in res_admin
    data = res_admin["data"]["operationsSummary"]
    assert data["overallStatus"] == "HEALTHY"
    assert data["services"][0]["serviceName"] == "gateway"
    assert data["telemetryTools"][0]["name"] == "Grafana"


def test_query_depth_limiter() -> None:
    from pathlib import Path

    from graphql import parse, validate
    from strawberry.extensions.query_depth_limiter import create_validator

    from app.schema import schema

    depths: dict[str, int] = {}
    validator = create_validator(
        max_depth=4, should_ignore=None, callback=lambda d: depths.update(d)
    )

    # 1. Test all actual frontend GraphQL operations including fragments
    ops_dir = Path(__file__).parents[2] / "frontend" / "src" / "graphql" / "operations"
    if ops_dir.exists():
        graphql_files = list(ops_dir.glob("*.graphql"))
        assert len(graphql_files) >= 9
        for f in sorted(graphql_files):
            content = f.read_text(encoding="utf-8")
            doc = parse(content)
            errors = validate(schema._schema, doc, [validator])
            assert not errors, f"GraphQL operation in {f.name} failed depth validation: {errors}"
            for op_name, depth in depths.items():
                assert depth <= 3, f"Operation {op_name} in {f.name} has depth {depth} > 3"

    # 2. Test valid query using fragment spread
    valid_fragment_query = """
    fragment ProjectFields on Project {
        id
        name
        status
    }
    query GetProjects {
        projects {
            items {
                ...ProjectFields
            }
        }
    }
    """
    doc_valid = parse(valid_fragment_query)
    depths.clear()
    errors_valid = validate(schema._schema, doc_valid, [validator])
    assert not errors_valid
    assert depths.get("GetProjects") == 2

    # 3. Test invalid query exceeding depth limit via fragment
    deep_fragment_query = """
    fragment DeepTask on Task {
        project {
            members {
                employee {
                    id
                }
            }
        }
    }
    query DeepQuery {
        tasks {
            items {
                ...DeepTask
            }
        }
    }
    """
    doc_deep = parse(deep_fragment_query)
    errors_deep = validate(schema._schema, doc_deep, [validator])
    assert len(errors_deep) == 1
    assert "exceeds maximum operation depth of 4" in errors_deep[0].message


def test_http_observability_middleware_and_metrics() -> None:
    import asyncio

    import httpx

    from app.config import settings
    from app.main import app

    async def _call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.get(
                "/health/live",
                headers={
                    "X-Correlation-ID": "test-custom-correlation-id",
                    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
                },
            )
            # Unauthorized request without scrape credential
            r_unauth = await client.get("/metrics")

            # Authorized request with Bearer token
            r_auth = await client.get(
                "/metrics",
                headers={"Authorization": f"Bearer {settings.gateway_metrics_token}"},
            )

            # Authorized request with X-Metrics-Token header
            r_header = await client.get(
                "/metrics",
                headers={"X-Metrics-Token": settings.gateway_metrics_token},
            )
            return r1, r_unauth, r_auth, r_header

    resp_live, resp_unauth, resp_auth, resp_header = asyncio.run(_call())
    assert resp_live.status_code == 200
    assert resp_live.headers["X-Correlation-ID"] == "test-custom-correlation-id"
    assert "traceparent" in resp_live.headers
    assert resp_live.headers["traceparent"].startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
    assert resp_live.headers["X-Content-Type-Options"] == "nosniff"

    # Unauthorized requests fail closed with 401
    assert resp_unauth.status_code == 401
    assert resp_unauth.headers.get("WWW-Authenticate") == "Bearer"
    assert "Unauthorized" in resp_unauth.text

    # Authorized requests with dedicated token succeed with 200
    assert resp_auth.status_code == 200
    assert "http_requests_total" in resp_auth.text
    assert resp_header.status_code == 200
    assert "http_requests_total" in resp_header.text


def test_business_request_with_failing_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    import httpx

    from app.main import app
    from app.observability import BoundedOTLPTraceExporter, telemetry

    failing_exporter = BoundedOTLPTraceExporter(
        endpoint="http://127.0.0.1:59999/unreachable", service_name="gateway"
    )
    monkeypatch.setattr(telemetry, "exporter", failing_exporter)

    async def _call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health/live")

    resp = asyncio.run(_call())
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}
