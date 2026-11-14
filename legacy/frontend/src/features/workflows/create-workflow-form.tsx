"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const mutation = `mutation CreateWorkflowRule($input:CreateWorkflowRuleInput!){createWorkflowRule(input:$input){id}}`;
export function CreateWorkflowForm() {
  const router = useRouter();
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!/^[0-9a-f-]{36}$/i.test(projectId) || !name.trim()) {
      setError("Enter a valid project UUID and rule name.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/graphql", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          query: mutation,
          variables: {
            input: {
              projectId,
              name,
              triggerType: "TASK_COMPLETED",
              actionType: "PROJECT_TASK_EXPORT",
              enabled: true,
            },
          },
        }),
      });
      const value = await response.json();
      if (value.errors) throw new Error();
      router.push(`/workflows/${value.data.createWorkflowRule.id}`);
    } catch {
      setError("The workflow rule could not be created.");
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="max-w-2xl space-y-5">
      <div>
        <p className="eyebrow">Workflow automation</p>
        <h1 className="mt-2 text-3xl font-semibold">Create rule</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Phase 10 supports one trigger and action: task completion submits a
          project task export in CSV format.
        </p>
      </div>
      <label className="block text-sm font-medium">
        Rule name
        <input
          className="mt-2 w-full rounded-md border px-3 py-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
        />
      </label>
      <label className="block text-sm font-medium">
        Project UUID
        <input
          className="mt-2 w-full rounded-md border px-3 py-2"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        />
      </label>
      <label className="block text-sm font-medium">
        Trigger
        <select className="mt-2 w-full rounded-md border px-3 py-2" disabled>
          <option>Task completed</option>
        </select>
      </label>
      <label className="block text-sm font-medium">
        Action
        <select className="mt-2 w-full rounded-md border px-3 py-2" disabled>
          <option>Project task export (CSV)</option>
        </select>
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button disabled={busy}>{busy ? "Creating…" : "Create rule"}</Button>
    </form>
  );
}
