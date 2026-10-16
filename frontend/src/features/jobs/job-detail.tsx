"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  JobDetailDocument,
  type JobDetailQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function JobDetail({ id }: { id: string }) {
  const [data, setData] = useState<JobDetailQuery["job"] | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const load = useCallback(async () => {
    setState("loading");
    try {
      setData((await requestGraphQL(JobDetailDocument, { id })).job);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [id]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold">Project task export</h1>
        <Badge>{data.status}</Badge>
      </div>
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
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            No execution attempts yet. Worker execution is introduced in Phase
            7.
          </p>
        )}
      </Card>
      <p className="text-sm text-muted-foreground">
        Dispatch, retry, cancellation, progress, and results become available
        with worker execution in Phase 7.
      </p>
    </div>
  );
}
