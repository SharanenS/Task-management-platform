"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";

type Rule = {
  id: string;
  projectId: string;
  name: string;
  enabled: boolean;
  triggerType: string;
  actionType: string;
};

const query = `query WorkflowRules($first:Int!,$after:String,$projectId:ID,$enabled:Boolean){workflowRules(first:$first,after:$after,projectId:$projectId,enabled:$enabled){nodes{id projectId name enabled triggerType actionType}pageInfo{hasNextPage endCursor}}}`;

export function WorkflowDirectory() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [enabled, setEnabled] = useState("");
  const load = useCallback(async () => {
    setError(false);
    try {
      const response = await fetch("/graphql", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          query,
          variables: {
            first: 20,
            projectId: projectId || null,
            enabled: enabled === "" ? null : enabled === "true",
          },
        }),
      });
      const value = await response.json();
      if (value.errors) throw new Error();
      setRules(value.data.workflowRules.nodes);
    } catch {
      setError(true);
      setRules([]);
    }
  }, [projectId, enabled]);
  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);
  return (
    <section aria-labelledby="workflow-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Phase 10</p>
          <h1 id="workflow-heading" className="mt-2 text-3xl font-semibold">
            Workflow automation
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Create bounded rules that export project tasks when a task reaches
            Done. Delivery is at least once; execution idempotency prevents
            duplicate logical jobs.
          </p>
        </div>
        <Button asChild>
          <Link href="/workflows/new">Create rule</Link>
        </Button>
      </div>
      <div className="mt-8 flex flex-wrap gap-3">
        <label className="text-sm">
          Project UUID
          <input
            aria-label="Project filter"
            className="ml-2 rounded-md border px-3 py-2"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          />
        </label>
        <label className="text-sm">
          State
          <select
            aria-label="Rule state"
            className="ml-2 rounded-md border px-3 py-2"
            value={enabled}
            onChange={(event) => setEnabled(event.target.value)}
          >
            <option value="">All</option>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </label>
      </div>
      {rules === null && (
        <div aria-label="Loading workflows" className="mt-8 space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}
      {error && (
        <ErrorState
          title="Unable to load workflows"
          description="Workflow automation is temporarily unavailable."
          onRetry={() => void load()}
        />
      )}
      {!error && rules?.length === 0 && (
        <EmptyState
          title="No workflow rules"
          description="Create a task-completion export rule for a project you manage."
        />
      )}
      <div className="mt-6 grid gap-4">
        {rules?.map((rule) => (
          <Link
            key={rule.id}
            href={`/workflows/${rule.id}`}
            className="rounded-xl border bg-card p-5 hover:border-primary"
          >
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold">{rule.name}</h2>
              <Badge>{rule.enabled ? "Enabled" : "Disabled"}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Task completed → Project task export (CSV)
            </p>
            <p className="mt-2 break-all text-xs text-muted-foreground">
              Project {rule.projectId}
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}
