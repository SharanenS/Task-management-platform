"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  JobsDocument,
  type JobStatus,
  type JobType,
  type JobsQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function JobDirectory() {
  const [data, setData] = useState<JobsQuery["jobs"] | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [status, setStatus] = useState<JobStatus | "">("");
  const [jobType, setJobType] = useState<JobType | "">("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<string | null>>([]);
  const load = useCallback(async () => {
    setState("loading");
    try {
      const result = await requestGraphQL(JobsDocument, {
        first: 20,
        after: cursor,
        status: status || null,
        jobType: jobType || null,
      });
      setData(result.jobs);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [cursor, jobType, status]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-widest text-primary uppercase">
            Jobs
          </p>
          <h1 className="text-3xl font-semibold">Durable job submissions</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Jobs are stored as submitted. Worker execution begins in Phase 7.
          </p>
        </div>
        <Button asChild>
          <Link href="/jobs/new">Submit job</Link>
        </Button>
      </div>
      <Card className="flex flex-wrap gap-3 p-4">
        <label className="text-sm">
          Status
          <select
            aria-label="Job status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as JobStatus | "");
              setCursor(null);
              setHistory([]);
            }}
            className="ml-2 h-10 rounded-lg border px-3"
          >
            <option value="">All</option>
            <option value="SUBMITTED">SUBMITTED</option>
          </select>
        </label>
        <label className="text-sm">
          Type
          <select
            aria-label="Job type"
            value={jobType}
            onChange={(event) => {
              setJobType(event.target.value as JobType | "");
              setCursor(null);
              setHistory([]);
            }}
            className="ml-2 h-10 rounded-lg border px-3"
          >
            <option value="">All</option>
            <option value="PROJECT_TASK_EXPORT">PROJECT_TASK_EXPORT</option>
          </select>
        </label>
      </Card>
      {state === "loading" && (
        <Card aria-label="Loading jobs" className="space-y-3 p-6">
          <Skeleton className="h-8" />
          <Skeleton className="h-20" />
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load jobs"
          description="Job management is temporarily unavailable."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" &&
        data &&
        (data.nodes.length ? (
          <div className="space-y-3">
            {data.nodes.map((job) => (
              <Link key={job.id} href={`/jobs/${job.id}`} className="block">
                <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:border-primary/40">
                  <div>
                    <h2 className="font-medium">Project task export</h2>
                    <p className="text-xs text-muted-foreground">
                      Project {job.payload.projectId}
                    </p>
                  </div>
                  <Badge>{job.status}</Badge>
                </Card>
              </Link>
            ))}
            <div className="flex gap-2">
              <Button
                variant="outline"
                disabled={!history.length}
                onClick={() => {
                  const previous = history.at(-1) ?? null;
                  setHistory((values) => values.slice(0, -1));
                  setCursor(previous);
                }}
              >
                Previous page
              </Button>
              <Button
                variant="outline"
                disabled={!data.pageInfo.hasNextPage}
                onClick={() => {
                  setHistory((values) => [...values, cursor]);
                  setCursor(data.pageInfo.endCursor ?? null);
                }}
              >
                Next page
              </Button>
            </div>
          </div>
        ) : (
          <EmptyState
            title="No jobs found"
            description="Submit a job or adjust the filters."
          />
        ))}
    </div>
  );
}
