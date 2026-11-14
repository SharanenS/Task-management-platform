"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  ReportArtifactDocument,
  ReportDocument,
  type ReportQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function ReportDetail({ id }: { id: string }) {
  const [report, setReport] = useState<ReportQuery["report"] | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const load = useCallback(async () => {
    setState("loading");
    try {
      setReport((await requestGraphQL(ReportDocument, { id })).report);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [id]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  const download = async () => {
    const artifact = (await requestGraphQL(ReportArtifactDocument, { id }))
      .reportArtifact;
    const blob = new Blob([artifact.content], { type: artifact.contentType });
    const url = URL.createObjectURL(blob);
    try {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.filename;
      anchor.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  };
  if (state === "loading")
    return (
      <Card aria-label="Loading report" className="p-6">
        <Skeleton className="h-24" />
      </Card>
    );
  if (state === "error" || !report)
    return (
      <ErrorState
        title="Unable to load report"
        description="The report is unavailable or access is not permitted."
        onRetry={() => void load()}
      />
    );
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-widest text-primary uppercase">
          Report
        </p>
        <h1 className="text-3xl font-semibold">Project task export</h1>
      </div>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Status</h2>
          <Badge>{report.status}</Badge>
        </div>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Project</dt>
            <dd>{report.payload.projectId}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Requested</dt>
            <dd>{new Date(report.createdAt).toLocaleString()}</dd>
          </div>
          {report.resultRowCount != null && (
            <div>
              <dt className="text-muted-foreground">Rows</dt>
              <dd>{report.resultRowCount}</dd>
            </div>
          )}
          {report.resultChecksum && (
            <div>
              <dt className="text-muted-foreground">Checksum</dt>
              <dd className="break-all font-mono text-xs">
                {report.resultChecksum}
              </dd>
            </div>
          )}
        </dl>
        {report.status === "FAILED" && (
          <p role="alert">
            The report failed: {report.failureClassification ?? "REPORT_FAILED"}
          </p>
        )}
        {report.status === "SUCCEEDED" && (
          <Button onClick={() => void download()}>Download CSV</Button>
        )}
        {!["SUCCEEDED", "FAILED"].includes(report.status) && (
          <p className="text-sm text-muted-foreground">
            Processing continues asynchronously. Refresh to see the latest
            state.
          </p>
        )}
      </Card>
    </div>
  );
}
