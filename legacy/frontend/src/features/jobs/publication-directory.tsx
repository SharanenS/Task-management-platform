"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  JobPublicationsDocument,
  type JobPublicationsQuery,
  type PublicationStatus,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function PublicationDirectory() {
  const [data, setData] = useState<
    JobPublicationsQuery["jobPublications"] | null
  >(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [status, setStatus] = useState<PublicationStatus | "">("");
  const load = useCallback(
    async (after?: string) => {
      setState("loading");
      try {
        setData(
          (
            await requestGraphQL(JobPublicationsDocument, {
              first: 20,
              after,
              status: status || undefined,
            })
          ).jobPublications,
        );
        setState("ready");
      } catch {
        setState("error");
      }
    },
    [status],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (state === "loading") return <Skeleton className="h-52" />;
  if (state === "error")
    return (
      <ErrorState
        title="Unable to load publications"
        description="Publication diagnostics are temporarily unavailable."
        onRetry={() => void load()}
      />
    );
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Publication diagnostics</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Durable job publication events and scheduled recovery.
        </p>
      </div>
      <label className="block max-w-xs text-sm">
        Status
        <select
          className="mt-2 w-full rounded-md border bg-background p-2"
          value={status}
          onChange={(event) =>
            setStatus(event.target.value as PublicationStatus | "")
          }
        >
          <option value="">All</option>
          {[
            "PENDING",
            "IN_FLIGHT",
            "FAILED",
            "PUBLISHED",
            "RECONCILIATION_REQUIRED",
          ].map((value) => (
            <option key={value} value={value}>
              {value.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      {data?.nodes.length ? (
        <div className="space-y-3">
          {data.nodes.map((item) => (
            <Card key={item.id} className="p-4">
              <strong>
                {item.status === "FAILED"
                  ? "Retry scheduled"
                  : item.status.replaceAll("_", " ")}
              </strong>
              <p className="mt-1 text-sm">Attempts: {item.attemptCount}</p>
              {item.lastFailureClassification ? (
                <p className="text-sm text-muted-foreground">
                  {item.lastFailureClassification}
                </p>
              ) : null}
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-6">No publication events match this filter.</Card>
      )}
      {data?.pageInfo.hasNextPage && data.pageInfo.endCursor ? (
        <Button
          variant="outline"
          onClick={() => void load(data.pageInfo.endCursor ?? undefined)}
        >
          Next page
        </Button>
      ) : null}
    </div>
  );
}
