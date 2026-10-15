"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  CreateTaskDocument,
  type TaskPriority,
} from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

export function CreateTaskForm({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  return (
    <Card className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-semibold">Create task</h1>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          if (submitting) return;
          setSubmitting(true);
          setMessage(null);
          const data = new FormData(event.currentTarget);
          try {
            const result = await requestGraphQL(CreateTaskDocument, {
              projectId,
              input: {
                title: String(data.get("title")),
                description: String(data.get("description")) || null,
                priority: String(data.get("priority")) as TaskPriority,
                assigneeEmployeeId: null,
                dueDate: String(data.get("dueDate")) || null,
              },
            });
            router.push(`/projects/${projectId}/tasks/${result.createTask.id}`);
          } catch (error) {
            setMessage(
              error instanceof GraphQLRequestError
                ? error.message
                : "The task could not be created.",
            );
            setSubmitting(false);
          }
        }}
      >
        <label className="block text-sm font-medium">
          Title
          <input
            name="title"
            required
            maxLength={200}
            className="mt-2 h-10 w-full rounded-lg border px-3"
          />
        </label>
        <label className="block text-sm font-medium">
          Description
          <textarea
            name="description"
            maxLength={8000}
            rows={5}
            className="mt-2 w-full rounded-lg border p-3"
          />
        </label>
        <label className="block text-sm font-medium">
          Priority
          <select
            name="priority"
            defaultValue="MEDIUM"
            className="mt-2 h-10 w-full rounded-lg border px-3"
          >
            <option>LOW</option>
            <option>MEDIUM</option>
            <option>HIGH</option>
            <option>URGENT</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          Due date
          <input
            name="dueDate"
            type="date"
            className="mt-2 h-10 w-full rounded-lg border px-3"
          />
        </label>
        {message && (
          <p role="alert" className="text-sm">
            {message}
          </p>
        )}
        <Button disabled={submitting}>
          {submitting ? "Creating…" : "Create task"}
        </Button>
      </form>
    </Card>
  );
}
