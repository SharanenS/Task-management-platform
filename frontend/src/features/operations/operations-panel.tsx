"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  ExternalLink,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  OperationsSummaryDocument,
  type OperationsSummaryQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

type OperationsData = NonNullable<OperationsSummaryQuery["operationsSummary"]>;

const SERVICE_DISPLAY_NAMES: Record<string, string> = {
  gateway: "Gateway",
  work: "Work Service",
  job: "Job Service",
  employee: "Employee Service",
  workflow: "Workflow Service",
  notification: "Notification Service",
};

function statusTone(
  status: string,
): "success" | "warning" | "danger" | "neutral" {
  if (status === "HEALTHY") return "success";
  if (status === "DEGRADED") return "warning";
  if (status === "UNAVAILABLE") return "danger";
  return "neutral";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "HEALTHY") {
    return (
      <CheckCircle2 className="size-3.5 text-emerald-600" aria-hidden="true" />
    );
  }
  if (status === "DEGRADED") {
    return (
      <AlertTriangle className="size-3.5 text-amber-600" aria-hidden="true" />
    );
  }
  return <XCircle className="size-3.5 text-rose-600" aria-hidden="true" />;
}

function formatAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "None";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600)
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function OperationsPanel() {
  const [data, setData] = useState<OperationsData | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
      setRefreshError(null);
    } else {
      setState("loading");
    }
    try {
      const res = await requestGraphQL(OperationsSummaryDocument);
      if (res.operationsSummary) {
        setData(res.operationsSummary);
        setState("ready");
      } else {
        throw new Error("No operations data returned");
      }
    } catch (err: unknown) {
      if (isRefresh) {
        setRefreshError(
          err instanceof Error ? err.message : "Failed to refresh telemetry.",
        );
      } else {
        setState("error");
      }
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (state === "loading") {
    return (
      <div
        className="space-y-6"
        role="status"
        aria-label="Loading operations telemetry"
      >
        <Skeleton className="h-28 w-full" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (state === "error" || !data) {
    return (
      <ErrorState
        title="Unable to load operations summary"
        description="Operational telemetry is temporarily unavailable or requires administrator authorization."
        onRetry={() => void load(false)}
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              Operations & Telemetry
            </h1>
            <Badge
              tone={statusTone(data.overallStatus)}
              className="capitalize text-xs font-semibold"
            >
              <StatusIcon status={data.overallStatus} />
              {data.overallStatus.toLowerCase()}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Platform service health, job execution diagnostics, queue
            observations, and telemetry tooling.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="size-3.5" aria-hidden="true" />
            <span>Updated {formatTime(data.generatedAt)}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5"
          >
            <RefreshCw
              className={`size-3.5 ${refreshing ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {refreshError && (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
        >
          {refreshError}
        </div>
      )}

      {/* Services Health Matrix */}
      <section aria-labelledby="services-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Server className="size-4 text-primary" aria-hidden="true" />
          <h2
            id="services-heading"
            className="text-lg font-semibold text-foreground"
          >
            Service Health Matrix
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.services.map((svc) => (
            <Card
              key={svc.serviceName}
              className="p-4 transition-shadow hover:shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium text-foreground">
                    {SERVICE_DISPLAY_NAMES[svc.serviceName.toLowerCase()] ??
                      svc.serviceName}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {svc.version ? `v${svc.version}` : "Internal Service"}
                  </p>
                </div>
                <Badge
                  tone={statusTone(svc.status)}
                  className="capitalize text-xs"
                >
                  <StatusIcon status={svc.status} />
                  {svc.status.toLowerCase()}
                </Badge>
              </div>

              <div className="mt-4 space-y-2 text-xs border-t pt-3">
                <div className="text-muted-foreground font-medium">
                  Dependencies
                </div>
                {svc.dependencies.map((dep, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-muted-foreground"
                  >
                    <span className="truncate">{dep.name}</span>
                    <div className="flex items-center gap-2">
                      {dep.latencyMs !== null &&
                        dep.latencyMs !== undefined && (
                          <span className="font-mono text-[11px] text-muted-foreground/80">
                            {dep.latencyMs}ms
                          </span>
                        )}
                      <Badge
                        tone={statusTone(dep.status)}
                        className="text-[10px] px-1.5 py-0.5"
                      >
                        {dep.status.toLowerCase()}
                      </Badge>
                    </div>
                  </div>
                ))}
                {svc.dependencies.length === 0 && (
                  <p className="text-muted-foreground/70 italic">
                    No external dependencies
                  </p>
                )}
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Job Operations Diagnostics */}
      <section aria-labelledby="job-ops-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Cpu className="size-4 text-primary" aria-hidden="true" />
          <h2
            id="job-ops-heading"
            className="text-lg font-semibold text-foreground"
          >
            Job Operations Diagnostics
          </h2>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">Pending</p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">
              {data.jobOperations.pendingCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Submitted & Queued
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">Running</p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-primary">
              {data.jobOperations.runningCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              In active execution
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">
              Completed
            </p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-emerald-600">
              {data.jobOperations.completedCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Terminal success
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">Failed</p>
            <p
              className={`mt-2 text-2xl font-bold tracking-tight ${
                data.jobOperations.failedCount > 0
                  ? "text-rose-600"
                  : "text-foreground"
              }`}
            >
              {data.jobOperations.failedCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Terminal failures
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">
              Cancelled
            </p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">
              {data.jobOperations.cancelledCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              User requested
            </p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-xs text-muted-foreground font-medium">
              Exhausted
            </p>
            <p
              className={`mt-2 text-2xl font-bold tracking-tight ${
                data.jobOperations.exhaustedCount > 0
                  ? "text-amber-600"
                  : "text-foreground"
              }`}
            >
              {data.jobOperations.exhaustedCount}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Max retries exceeded
            </p>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">
                Oldest Pending Job Age
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Latency since submission for oldest unfinished work
              </p>
            </div>
            <div className="font-mono text-lg font-semibold text-foreground">
              {formatAge(data.jobOperations.oldestPendingAgeSeconds)}
            </div>
          </Card>
          <Card className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">
                Recent Failures (Last 24h)
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Failures requiring operator review or automatic retry
              </p>
            </div>
            <Badge
              tone={
                data.jobOperations.recentFailuresCount > 0
                  ? "warning"
                  : "success"
              }
              className="font-mono text-sm px-2.5 py-1"
            >
              {data.jobOperations.recentFailuresCount}
            </Badge>
          </Card>
        </div>
      </section>

      {/* Queue & Outbox Observations */}
      <section aria-labelledby="queues-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-primary" aria-hidden="true" />
          <h2
            id="queues-heading"
            className="text-lg font-semibold text-foreground"
          >
            Queues & Outbox Observations
          </h2>
        </div>
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/40 text-xs text-muted-foreground font-medium">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Queue / Outbox Stream
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Type
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Ready Messages
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    In-Flight / Unack
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Consumers
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Measured At
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.queues.map((q) => {
                  const isOutbox = q.queueName.includes("outbox");
                  const isUnavailable =
                    q.messagesReady === null || q.messagesReady === undefined;
                  return (
                    <tr key={q.queueName} className="hover:bg-muted/20">
                      <td className="px-4 py-3 font-mono text-xs font-medium text-foreground">
                        {q.queueName}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {isOutbox ? (
                          <span className="inline-flex items-center rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">
                            Database Outbox
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                            Broker Queue
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {isUnavailable ? (
                          <span className="text-amber-600 font-sans text-xs">
                            Unavailable
                          </span>
                        ) : (
                          q.messagesReady
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {isUnavailable ||
                        q.messagesUnacknowledged === null ||
                        q.messagesUnacknowledged === undefined ? (
                          <span className="text-amber-600 font-sans text-xs">
                            Unavailable
                          </span>
                        ) : (
                          q.messagesUnacknowledged
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs">
                        {isUnavailable ||
                        q.consumersCount === null ||
                        q.consumersCount === undefined ? (
                          <span className="text-amber-600 font-sans text-xs">
                            Unavailable
                          </span>
                        ) : (
                          <span
                            className={
                              (q.consumersCount ?? 0) > 0
                                ? "text-emerald-700 font-semibold"
                                : "text-muted-foreground"
                            }
                          >
                            {q.consumersCount}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-muted-foreground">
                        {formatTime(q.measuredAt)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* Local Telemetry Tooling Links */}
      <section aria-labelledby="tooling-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
          <h2
            id="tooling-heading"
            className="text-lg font-semibold text-foreground"
          >
            Local Observability Tooling
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {data.telemetryTools.map((tool) => (
            <Card
              key={tool.name}
              className="p-4 flex flex-col justify-between hover:shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-foreground">{tool.name}</h3>
                  <ExternalLink
                    className="size-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                </div>
                <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                  {tool.description}
                </p>
              </div>
              <div className="mt-4 pt-3 border-t">
                <a
                  href={tool.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  <span>Open {tool.name}</span>
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
