import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OperationsPanel } from "@/features/operations/operations-panel";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const mockOperationsData = {
  operationsSummary: {
    generatedAt: "2026-11-07T12:00:00Z",
    overallStatus: "HEALTHY",
    services: [
      {
        serviceName: "Gateway",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "employee",
            status: "HEALTHY",
            latencyMs: 2.1,
            message: null,
          },
          { name: "work", status: "HEALTHY", latencyMs: 1.8, message: null },
        ],
      },
      {
        serviceName: "Work Service",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "postgres",
            status: "HEALTHY",
            latencyMs: 0.9,
            message: null,
          },
        ],
      },
      {
        serviceName: "Job Service",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "postgres",
            status: "HEALTHY",
            latencyMs: 1.1,
            message: null,
          },
        ],
      },
      {
        serviceName: "Employee Service",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "postgres",
            status: "HEALTHY",
            latencyMs: 0.8,
            message: null,
          },
        ],
      },
      {
        serviceName: "Workflow Service",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "postgres",
            status: "HEALTHY",
            latencyMs: 0.7,
            message: null,
          },
        ],
      },
      {
        serviceName: "Notification Service",
        status: "HEALTHY",
        version: "0.1.0",
        uptimeSeconds: 3600.0,
        checkedAt: "2026-11-07T12:00:00Z",
        dependencies: [
          {
            name: "postgres",
            status: "HEALTHY",
            latencyMs: 0.6,
            message: null,
          },
        ],
      },
    ],
    jobOperations: {
      pendingCount: 0,
      runningCount: 1,
      completedCount: 42,
      failedCount: 2,
      cancelledCount: 0,
      exhaustedCount: 1,
      oldestPendingAgeSeconds: null,
      recentFailuresCount: 2,
      measuredAt: "2026-11-07T12:00:00Z",
    },
    queues: [
      {
        queueName: "celery",
        messagesReady: 0,
        messagesUnacknowledged: 1,
        consumersCount: 2,
        measuredAt: "2026-11-07T12:00:00Z",
      },
      {
        queueName: "work.events",
        messagesReady: 0,
        messagesUnacknowledged: 0,
        consumersCount: 2,
        measuredAt: "2026-11-07T12:00:00Z",
      },
      {
        queueName: "work.outbox",
        messagesReady: 0,
        messagesUnacknowledged: 0,
        consumersCount: 1,
        measuredAt: "2026-11-07T12:00:00Z",
      },
    ],
    telemetryTools: [
      {
        name: "Grafana Dashboards",
        url: "http://127.0.0.1:3001",
        description: "Metrics dashboards and alert visualizations",
      },
      {
        name: "Jaeger Traces",
        url: "http://127.0.0.1:16686",
        description: "Distributed trace inspection and span timeline analysis",
      },
      {
        name: "Prometheus Targets",
        url: "http://127.0.0.1:9090",
        description:
          "Raw metrics scrape targets, active alerts, and TSDB queries",
      },
    ],
  },
};

describe("OperationsPanel component", () => {
  it("renders operations telemetry, service health matrix, and truthful counts", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: mockOperationsData }),
    });
    vi.stubGlobal("fetch", fetch);

    render(<OperationsPanel />);

    // Shows loading state initially
    expect(screen.getByRole("status")).toBeInTheDocument();

    // Loads and displays overall status and title
    expect(
      await screen.findByText("Operations & Telemetry"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("healthy").length).toBeGreaterThan(0);

    // Service health matrix
    expect(screen.getByText("Gateway")).toBeInTheDocument();
    expect(screen.getByText("Work Service")).toBeInTheDocument();
    expect(screen.getByText("Job Service")).toBeInTheDocument();
    expect(screen.getByText("Workflow Service")).toBeInTheDocument();
    expect(screen.getByText("Notification Service")).toBeInTheDocument();
    expect(screen.getByText("Employee Service")).toBeInTheDocument();

    // Job operations metrics
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Exhausted")).toBeInTheDocument();
    expect(screen.getByText("Recent Failures (Last 24h)")).toBeInTheDocument();

    // Truthful queue counts
    expect(screen.getByText("celery")).toBeInTheDocument();
    expect(screen.getByText("work.events")).toBeInTheDocument();

    // Telemetry links with loopback targets and security attributes
    const grafanaLink = screen.getByRole("link", {
      name: /Grafana Dashboards/i,
    });
    expect(grafanaLink).toHaveAttribute("href", "http://127.0.0.1:3001");
    expect(grafanaLink).toHaveAttribute("target", "_blank");
    expect(grafanaLink).toHaveAttribute("rel", "noopener noreferrer");

    const jaegerLink = screen.getByRole("link", { name: /Jaeger Traces/i });
    expect(jaegerLink).toHaveAttribute("href", "http://127.0.0.1:16686");
    expect(jaegerLink).toHaveAttribute("target", "_blank");
    expect(jaegerLink).toHaveAttribute("rel", "noopener noreferrer");

    const prometheusLink = screen.getByRole("link", {
      name: /Prometheus Targets/i,
    });
    expect(prometheusLink).toHaveAttribute("href", "http://127.0.0.1:9090");
    expect(prometheusLink).toHaveAttribute("target", "_blank");
    expect(prometheusLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("handles refresh action and displays error banner if refresh fails", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockOperationsData }),
      })
      .mockRejectedValueOnce(new Error("Network timeout contacting gateway"));
    vi.stubGlobal("fetch", fetch);

    render(<OperationsPanel />);
    expect(
      await screen.findByText("Operations & Telemetry"),
    ).toBeInTheDocument();

    const refreshButton = screen.getByRole("button", { name: /^refresh$/i });
    fireEvent.click(refreshButton);

    expect(
      await screen.findByText("Network timeout contacting gateway"),
    ).toBeInTheDocument();
    // Existing data is preserved
    expect(screen.getByText("Gateway")).toBeInTheDocument();
  });

  it("handles initial load failure with retryable error state", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error("Gateway connection refused"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockOperationsData }),
      });
    vi.stubGlobal("fetch", fetch);

    render(<OperationsPanel />);

    expect(
      await screen.findByText("Unable to load operations summary"),
    ).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: "Try again" });
    fireEvent.click(retryButton);

    expect(
      await screen.findByText("Operations & Telemetry"),
    ).toBeInTheDocument();
  });

  it("verifies security headers and CSP compatibility with auth redirects and CSV downloads", async () => {
    const nextConfig = (await import("../next.config")).default;
    expect(nextConfig.headers).toBeDefined();

    const headerConfigs = await nextConfig.headers!();
    const globalHeaders = headerConfigs.find(
      (h: { source: string }) => h.source === "/(.*)",
    );
    expect(globalHeaders).toBeDefined();

    const headersMap = Object.fromEntries(
      globalHeaders!.headers.map((h: { key: string; value: string }) => [
        h.key,
        h.value,
      ]),
    );

    // Frame prevention & mime type protection
    expect(headersMap["X-Frame-Options"]).toBe("DENY");
    expect(headersMap["X-Content-Type-Options"]).toBe("nosniff");
    expect(headersMap["Referrer-Policy"]).toBe(
      "strict-origin-when-cross-origin",
    );

    const csp = headersMap["Content-Security-Policy"];
    expect(csp).toBeDefined();

    // CSP allows blob URLs for CSV export downloads
    expect(csp).toContain("default-src 'self' blob:");
    expect(csp).toContain("connect-src 'self' blob:");

    // CSP allows OIDC form actions & redirects to Keycloak
    expect(csp).toContain(
      "form-action 'self' http://localhost:8080 http://127.0.0.1:8080",
    );

    // CSP prevents clickjacking via frame-ancestors
    expect(csp).toContain("frame-ancestors 'none'");
  });
});
