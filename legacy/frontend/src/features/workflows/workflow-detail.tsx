"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/states";

type Data = {
  workflowRule: {
    id: string;
    name: string;
    projectId: string;
    enabled: boolean;
    version: number;
  };
  workflowExecutions: {
    nodes: Array<{
      id: string;
      status: string;
      taskId: string;
      resultingJobId: string | null;
      failureClassification: string | null;
      createdAt: string;
    }>;
  };
};
const query = `query WorkflowRule($id:ID!){workflowRule(id:$id){id name projectId enabled version}workflowExecutions(first:20,ruleId:$id){nodes{id status taskId resultingJobId failureClassification createdAt}}}`;
const stateMutation = `mutation SetWorkflowRuleEnabled($ruleId:ID!,$enabled:Boolean!,$expectedVersion:Int!){setWorkflowRuleEnabled(ruleId:$ruleId,enabled:$enabled,expectedVersion:$expectedVersion){id enabled version}}`;
export function WorkflowDetail({ id }: { id: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const load = useCallback(async () => {
    setError(false);
    try {
      const response = await fetch("/graphql", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, variables: { id } }),
      });
      const value = await response.json();
      if (value.errors) throw new Error();
      setData(value.data);
    } catch {
      setError(true);
    }
  }, [id]);
  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);
  async function toggle() {
    if (!data) return;
    setConfirm(false);
    const response = await fetch("/graphql", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: stateMutation,
        variables: {
          ruleId: id,
          enabled: !data.workflowRule.enabled,
          expectedVersion: data.workflowRule.version,
        },
      }),
    });
    const value = await response.json();
    if (value.errors) {
      setError(true);
      return;
    }
    await load();
  }
  if (!data && !error)
    return (
      <div aria-label="Loading workflow">
        <Skeleton className="h-32" />
      </div>
    );
  if (error)
    return (
      <ErrorState
        title="Unable to load workflow"
        description="Reload and try again."
        onRetry={() => void load()}
      />
    );
  const rule = data!.workflowRule;
  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Workflow rule</p>
          <h1 className="mt-2 text-3xl font-semibold">{rule.name}</h1>
          <p className="mt-2 break-all text-sm text-muted-foreground">
            Project {rule.projectId}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge>{rule.enabled ? "Enabled" : "Disabled"}</Badge>
          <Button variant="outline" onClick={() => setConfirm(true)}>
            {rule.enabled ? "Disable" : "Enable"}
          </Button>
        </div>
      </div>
      {confirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          className="mt-6 rounded-xl border bg-card p-5"
        >
          <h2 id="confirm-title" className="font-semibold">
            {rule.enabled ? "Disable" : "Enable"} this workflow?
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Disabled rules do not create executions for later task completions.
          </p>
          <div className="mt-4 flex gap-2">
            <Button onClick={() => void toggle()}>Confirm</Button>
            <Button variant="outline" onClick={() => setConfirm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      <div className="mt-8 rounded-xl border bg-card p-5">
        <h2 className="font-semibold">Supported automation</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Task completed → Project task export (CSV). Publication is at least
          once; deterministic idempotency prevents duplicate logical jobs.
        </p>
      </div>
      <h2 className="mt-8 text-xl font-semibold">Execution history</h2>
      {data!.workflowExecutions.nodes.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No executions yet.</p>
      ) : (
        <div className="mt-4 grid gap-3">
          {data!.workflowExecutions.nodes.map((item) => (
            <article key={item.id} className="rounded-xl border bg-card p-4">
              <div className="flex flex-wrap justify-between gap-3">
                <span className="font-medium">{item.status}</span>
                <time className="text-xs text-muted-foreground">
                  {new Date(item.createdAt).toLocaleString()}
                </time>
              </div>
              <p className="mt-2 break-all text-xs text-muted-foreground">
                Task {item.taskId}
              </p>
              {item.resultingJobId && (
                <Link
                  className="mt-3 inline-block text-sm font-semibold text-primary"
                  href={`/jobs/${item.resultingJobId}`}
                >
                  Open resulting job
                </Link>
              )}
              {item.failureClassification && (
                <p className="mt-2 text-sm">Action is pending recovery.</p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
