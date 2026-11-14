"use client";
import {
  ArrowUpRight,
  CheckCircle2,
  Database,
  Globe2,
  Network,
  RefreshCw,
  Server,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { useSystemInfo } from "./use-system-info";

export function SystemPanel() {
  const query = useSystemInfo();
  const info = query.data?.systemInfo;
  return (
    <div className="space-y-7">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">A real connection</p>
          <h1 className="page-title">System status</h1>
          <p className="page-description">
            Live gateway diagnostics, directly from the GraphQL API.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
        >
          <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
          {query.isFetching ? "Checking…" : "Refresh status"}
        </Button>
      </section>
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b px-6 py-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Server className="size-4 text-primary" /> GraphQL gateway
          </h2>
          <Badge tone={query.isError ? "warning" : "neutral"}>Live data</Badge>
        </div>
        <div className="p-6" aria-live="polite">
          {query.isPending ? (
            <div
              role="status"
              aria-label="Connecting to gateway"
              className="space-y-4"
            >
              <Skeleton className="h-7 w-48" />
              <Skeleton className="h-4 w-64 max-w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : query.isError ? (
            <ErrorState
              title="Gateway unavailable"
              description="The latest request failed. Previously received data is not shown as healthy. Check that the gateway is running, then retry."
              onRetry={() => void query.refetch()}
              pending={query.isFetching}
            />
          ) : info ? (
            <>
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-1 size-6 text-primary" />
                <div>
                  <h3 className="text-xl font-semibold tracking-tight">
                    Gateway is reachable
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    The SystemInfo operation completed successfully.
                  </p>
                </div>
              </div>
              <dl className="mt-7 grid gap-5 rounded-lg border bg-background p-5 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  ["Service", info.name],
                  ["Version", info.version],
                  ["Environment", info.environment],
                  ["Gateway status", info.status],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="eyebrow">{label}</dt>
                    <dd className="mt-2 text-sm font-medium break-words">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="mt-4 text-xs text-muted-foreground">
                Last successful response:{" "}
                {new Date(query.dataUpdatedAt).toLocaleTimeString()}. Checked
                every 15 seconds while this page is active.
              </p>
            </>
          ) : null}
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-sm font-semibold">The Phase 1 request path</h2>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            One public business contract. No database needed for this foundation
            slice.
          </p>
          <div className="mt-6 space-y-3">
            {[
              {
                icon: Globe2,
                title: "Next.js frontend",
                subtitle: "TanStack Query + generated operation types",
              },
              {
                icon: Network,
                title: "Same-origin /graphql",
                subtitle: "Next.js forwards the request to the gateway",
              },
              {
                icon: Server,
                title: "FastAPI + Strawberry",
                subtitle: "Resolves non-sensitive gateway metadata",
              },
            ].map(({ icon: Icon, title, subtitle }, index) => (
              <div
                key={title}
                className="flex items-center gap-3 rounded-lg border p-4"
              >
                <Icon className="size-5 text-primary" />
                <div>
                  <p className="text-xs font-semibold">{title}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {subtitle}
                  </p>
                </div>
                <span className="ml-auto text-[10px] text-muted-foreground">
                  0{index + 1}
                </span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <h2 className="text-sm font-semibold">Service boundaries</h2>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Planned domains, introduced through future vertical slices.
          </p>
          <div className="mt-5 divide-y">
            {[
              "Identity / Employee",
              "Work Management",
              "Workflow",
              "Job Execution",
            ].map((name) => (
              <div key={name} className="flex items-center gap-3 py-4">
                <Database className="size-4 text-muted-foreground" />
                <span className="text-xs font-medium">{name}</span>
                <Badge className="ml-auto">Not started</Badge>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
            Each domain will own its PostgreSQL database and migrations. This
            indicator does not report domain-service, database, or worker
            health.
          </p>
        </Card>
      </div>
      <div className="flex gap-3 rounded-lg border border-dashed p-5">
        <ArrowUpRight className="size-4 shrink-0 text-primary" />
        <p className="text-xs leading-5 text-muted-foreground">
          <strong className="text-foreground">Try the recovery flow.</strong>{" "}
          Stop the gateway and refresh this page’s status. Restart it and
          refresh again. The indicator should move from unavailable to
          connected.
        </p>
      </div>
    </div>
  );
}
