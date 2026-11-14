"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SubmitProjectTaskExportDocument } from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function SubmitJobForm() {
  const router = useRouter();
  const key = useRef<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  return (
    <Card className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-semibold">Submit project task export</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        This stores a durable request only. No worker executes it during Phase
        6.
      </p>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          if (submitting) return;
          setSubmitting(true);
          setMessage(null);
          const data = new FormData(event.currentTarget);
          const projectId = String(data.get("projectId")).trim();
          if (!UUID_PATTERN.test(projectId)) {
            setMessage("Enter a valid project UUID.");
            setSubmitting(false);
            return;
          }
          key.current ??= `phase6-${crypto.randomUUID()}`;
          try {
            const result = await requestGraphQL(
              SubmitProjectTaskExportDocument,
              {
                input: {
                  projectId,
                  includeCompleted: data.get("includeCompleted") === "on",
                  idempotencyKey: key.current,
                },
              },
            );
            router.push(`/jobs/${result.submitProjectTaskExport.id}`);
          } catch (error) {
            setMessage(
              error instanceof GraphQLRequestError
                ? error.message
                : "The job could not be submitted. Retry uses the same request key.",
            );
            setSubmitting(false);
          }
        }}
      >
        <label className="block text-sm font-medium">
          Project UUID
          <input
            name="projectId"
            required
            maxLength={36}
            autoComplete="off"
            className="mt-2 h-10 w-full rounded-lg border px-3"
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input name="includeCompleted" type="checkbox" defaultChecked />
          Include completed tasks
        </label>
        <p className="text-sm text-muted-foreground">Format: CSV</p>
        {message && (
          <p role="alert" className="text-sm">
            {message}
          </p>
        )}
        <Button disabled={submitting}>
          {submitting ? "Submitting…" : "Submit job"}
        </Button>
      </form>
    </Card>
  );
}
