"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  ProjectDirectoryDocument,
  ReportsDocument,
  RequestProjectTaskReportDocument,
  type ProjectDirectoryQuery,
  type ReportsQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function ReportCenter() {
  const [reports, setReports] = useState<ReportsQuery["reports"] | null>(null);
  const [projects, setProjects] = useState<
    ProjectDirectoryQuery["projects"]["nodes"]
  >([]);
  const [projectId, setProjectId] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [submitting, setSubmitting] = useState(false);
  const load = useCallback(async () => {
    setState("loading");
    try {
      const [reportData, projectData] = await Promise.all([
        requestGraphQL(ReportsDocument, {
          first: 20,
          after: null,
          status: null,
        }),
        requestGraphQL(ProjectDirectoryDocument, {
          first: 50,
          after: null,
          search: null,
          status: null,
        }),
      ]);
      setReports(reportData.reports);
      setProjects(projectData.projects.nodes);
      setProjectId((value) => value || projectData.projects.nodes[0]?.id || "");
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  const requestReport = async () => {
    if (!projectId) return;
    setSubmitting(true);
    try {
      await requestGraphQL(RequestProjectTaskReportDocument, {
        input: {
          projectId,
          includeCompleted: true,
          idempotencyKey: crypto.randomUUID(),
        },
      });
      await load();
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-widest text-primary uppercase">
          Reports
        </p>
        <h1 className="text-3xl font-semibold">Reports and exports</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Requests run asynchronously through the durable job pipeline.
        </p>
      </div>
      <Card className="space-y-4 p-5">
        <h2 className="font-semibold">Request project task report</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            Project
            <select
              aria-label="Report project"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="h-10 min-w-64 rounded-lg border px-3"
            >
              <option value="">Select a project</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.key} · {project.name}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            Report type
            <select
              aria-label="Report type"
              className="h-10 rounded-lg border px-3"
              disabled
            >
              <option>Project task export (CSV)</option>
            </select>
          </label>
          <Button
            disabled={!projectId || submitting}
            onClick={() => void requestReport()}
          >
            {submitting ? "Requesting…" : "Request report"}
          </Button>
        </div>
      </Card>
      {state === "loading" && (
        <Card aria-label="Loading reports" className="space-y-3 p-6">
          <Skeleton className="h-8" />
          <Skeleton className="h-20" />
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load reports"
          description="Reports are temporarily unavailable."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" &&
        reports &&
        (reports.nodes.length ? (
          <div className="space-y-3">
            {reports.nodes.map((report) => (
              <Link
                key={report.id}
                href={`/reports/${report.id}`}
                className="block"
              >
                <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:border-primary/40">
                  <div>
                    <h2 className="font-medium">Project task report</h2>
                    <p className="text-xs text-muted-foreground">
                      Requested {new Date(report.createdAt).toLocaleString()}
                    </p>
                  </div>
                  <Badge>{report.status}</Badge>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No reports"
            description="Request a project task report to begin."
          />
        ))}
    </div>
  );
}
