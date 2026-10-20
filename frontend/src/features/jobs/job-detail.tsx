"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  JobDetailDocument,
  DispatchJobDocument,
  type JobDetailQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function JobDetail({ id }: { id: string }) {
  const [data, setData] = useState<JobDetailQuery["job"] | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [confirming, setConfirming] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const loadingRef = useRef(false);
  const dispatchButtonRef = useRef<HTMLButtonElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const load = useCallback(
    async (background = false) => {
      if (loadingRef.current) return;
      loadingRef.current = true;
      if (!background) setState("loading");
      try {
        setData((await requestGraphQL(JobDetailDocument, { id })).job);
        setState("ready");
      } catch {
        if (!background) setState("error");
      } finally {
        loadingRef.current = false;
      }
    },
    [id],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    if (!data || !["QUEUED", "RUNNING"].includes(data.status)) return;
    const timer = window.setInterval(() => void load(true), 2_000);
    return () => clearInterval(timer);
  }, [data, load]);
  useEffect(() => {
    if (confirming) confirmButtonRef.current?.focus();
  }, [confirming]);
  const closeConfirmation = () => {
    setConfirming(false);
    window.setTimeout(() => dispatchButtonRef.current?.focus(), 0);
  };
  const dispatch = async () => {
    if (!data || dispatching) return;
    setDispatching(true);
    setActionError(null);
    try {
      await requestGraphQL(DispatchJobDocument, {
        jobId: data.id,
        expectedVersion: data.version,
      });
      closeConfirmation();
      await load(true);
    } catch {
      setActionError("The job could not be dispatched. Refresh and try again.");
    } finally {
      setDispatching(false);
    }
  };
  const download = () => {
    if (!data?.resultContent) return;
    const url = URL.createObjectURL(
      new Blob([data.resultContent], {
        type: data.resultContentType ?? "text/csv",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "project-task-export.csv";
    link.click();
    URL.revokeObjectURL(url);
  };
  if (state === "loading")
    return (
      <Card aria-label="Loading job" className="p-6">
        <Skeleton className="h-40" />
      </Card>
    );
  if (state === "error" || !data)
    return (
      <ErrorState
        title="Unable to load job"
        description="The job is unavailable or access is not permitted."
        onRetry={() => void load()}
      />
    );
  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold">Project task export</h1>
        <Badge>{data.status}</Badge>
        <Button variant="outline" onClick={() => void load()}>
          Refresh
        </Button>
        {data.status === "SUBMITTED" ? (
          <Button ref={dispatchButtonRef} onClick={() => setConfirming(true)}>
            Dispatch job
          </Button>
        ) : null}
      </div>
      {confirming ? (
        <Card
          role="dialog"
          aria-modal="true"
          aria-labelledby="dispatch-title"
          className="p-6"
          onKeyDown={(event) => {
            if (event.key === "Escape" && !dispatching) closeConfirmation();
          }}
        >
          <h2 id="dispatch-title" className="font-semibold">
            Dispatch this export?
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            The worker will read current project data and create a CSV result.
          </p>
          {actionError ? (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {actionError}
            </p>
          ) : null}
          <div className="mt-4 flex gap-3">
            <Button
              ref={confirmButtonRef}
              onClick={() => void dispatch()}
              disabled={dispatching}
            >
              {dispatching ? "Dispatching…" : "Confirm dispatch"}
            </Button>
            <Button
              variant="outline"
              onClick={closeConfirmation}
              disabled={dispatching}
            >
              Cancel
            </Button>
          </div>
        </Card>
      ) : null}
      <Card className="p-6">
        <h2 className="font-semibold">Submitted payload</h2>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Project</dt>
            <dd className="break-all">{data.payload.projectId}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Format</dt>
            <dd>{data.payload.format}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Completed tasks</dt>
            <dd>{data.payload.includeCompleted ? "Included" : "Excluded"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Version</dt>
            <dd>{data.version}</dd>
          </div>
        </dl>
      </Card>
      <Card className="p-6">
        <h2 className="font-semibold">Execution attempts</h2>
        {data.attempts.length ? (
          <ul className="mt-3 space-y-2">
            {data.attempts.map((attempt) => (
              <li key={attempt.id}>
                Attempt {attempt.attemptNumber}: {attempt.status}
                {attempt.safeSummary ? ` — ${attempt.safeSummary}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            No execution attempts yet.
          </p>
        )}
      </Card>
      {data.status === "SUCCEEDED" && data.resultContent ? (
        <Card className="min-w-0 p-6">
          <h2 className="font-semibold">Export result</h2>
          <p className="mt-2 break-all text-sm text-muted-foreground">
            {data.resultRowCount ?? 0} rows · integrity {data.resultChecksum}
          </p>
          {data.resultTruncated ? (
            <p role="status" className="mt-2 text-sm">
              The export reached its configured row limit.
            </p>
          ) : null}
          <Button className="mt-4" onClick={download}>
            Download CSV
          </Button>
          <pre className="mt-4 max-h-72 w-full max-w-full overflow-auto rounded-lg bg-muted p-4 text-xs">
            {data.resultContent}
          </pre>
        </Card>
      ) : null}
      {data.status === "FAILED" ? (
        <Card className="p-6" role="alert">
          <h2 className="font-semibold">Execution failed</h2>
          <p className="mt-2 text-sm">
            {data.resultSummary ?? "The export could not be completed."}
          </p>
          {data.failureClassification ? (
            <p className="mt-2 text-sm text-muted-foreground">
              Classification: {data.failureClassification}
            </p>
          ) : null}
        </Card>
      ) : null}
      <p className="text-sm text-muted-foreground">
        Dispatch uses direct broker publication. A rare failure between database
        commit and broker confirmation can require a manual retry.
      </p>
    </div>
  );
}
