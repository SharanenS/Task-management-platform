"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CreateProjectDocument } from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

export function CreateProjectForm() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  return (
    <Card className="max-w-2xl p-6">
      <form
        className="space-y-5"
        onSubmit={async (event) => {
          event.preventDefault();
          if (saving) return;
          setSaving(true);
          setMessage(null);
          const data = new FormData(event.currentTarget);
          try {
            const result = await requestGraphQL(CreateProjectDocument, {
              input: {
                key: String(data.get("key")),
                name: String(data.get("name")),
                description: String(data.get("description")) || null,
              },
            });
            router.push(`/projects/${result.createProject.id}`);
          } catch (error) {
            setMessage(
              error instanceof GraphQLRequestError
                ? error.message
                : "The project could not be created.",
            );
            setSaving(false);
          }
        }}
      >
        <label className="block text-sm font-medium">
          Project key
          <input
            name="key"
            required
            minLength={2}
            maxLength={32}
            pattern="[A-Za-z][A-Za-z0-9-]*"
            className="mt-2 h-10 w-full rounded-lg border bg-background px-3 uppercase focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block text-sm font-medium">
          Name
          <input
            name="name"
            required
            maxLength={200}
            className="mt-2 h-10 w-full rounded-lg border bg-background px-3 focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block text-sm font-medium">
          Description
          <textarea
            name="description"
            maxLength={4000}
            rows={5}
            className="mt-2 w-full rounded-lg border bg-background p-3 focus:ring-2 focus:ring-ring"
          />
        </label>
        {message && (
          <p role="alert" className="text-sm text-destructive">
            {message}
          </p>
        )}
        <Button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Create project"}
        </Button>
      </form>
    </Card>
  );
}
