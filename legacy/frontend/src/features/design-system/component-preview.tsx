"use client";
import { useState } from "react";
import { Check, MousePointer2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
export function ComponentPreview() {
  const [state, setState] = useState<"empty" | "loading" | "error" | "success">(
    "empty",
  );
  return (
    <div className="space-y-7">
      <div>
        <p className="eyebrow">Consistent by design</p>
        <h1 className="page-title">The interface toolkit</h1>
        <p className="page-description">
          A small set of reusable foundations for every feature to come.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-sm font-semibold">
            Quiet colors. Clear meaning.
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            Forest green anchors a neutral, focused workspace.
          </p>
          <div className="mt-6 grid grid-cols-4 gap-3">
            {[
              { name: "Primary", hex: "#21634F" },
              { name: "Ink", hex: "#222C2A" },
              { name: "Canvas", hex: "#F7F8FA" },
              { name: "Border", hex: "#E5E9E7" },
            ].map((color) => (
              <div key={color.name}>
                <div
                  className="h-20 rounded-lg border"
                  style={{ background: color.hex }}
                />
                <p className="mt-3 text-xs font-medium">{color.name}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {color.hex}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-7 flex flex-wrap gap-3 border-t pt-5">
            <Badge tone="success">Connected</Badge>
            <Badge tone="warning">Needs attention</Badge>
            <Badge>Not started</Badge>
          </div>
        </Card>
        <Card className="p-6">
          <h2 className="text-sm font-semibold">A deliberate hierarchy</h2>
          <p className="mt-2 text-xs text-muted-foreground">
            System typography. Readable at every screen size.
          </p>
          <div className="mt-6 space-y-4">
            <p className="eyebrow">Eyebrow · 10px</p>
            <p className="text-3xl font-semibold tracking-tight">
              A place for great work.
            </p>
            <p className="text-sm font-semibold">
              Section title · 14px semibold
            </p>
            <p className="max-w-sm text-sm leading-6 text-muted-foreground">
              Keep descriptions clear and useful. Use generous spacing to make
              the next step easy to find.
            </p>
          </div>
        </Card>
      </div>
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <MousePointer2 className="mt-0.5 size-4 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">
              States that tell the whole story
            </h2>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Interactive component previews only. These controls do not change
              backend data.
            </p>
          </div>
        </div>
        <div
          className="mt-5 flex flex-wrap gap-2"
          role="group"
          aria-label="Preview state"
        >
          {(["empty", "loading", "error", "success"] as const).map((option) => (
            <Button
              key={option}
              size="sm"
              variant={state === option ? "default" : "outline"}
              aria-pressed={state === option}
              onClick={() => setState(option)}
              className="capitalize"
            >
              {option}
            </Button>
          ))}
          <Button size="sm" disabled variant="outline">
            Unavailable
          </Button>
        </div>
        <div
          className="mt-6 min-h-56 rounded-xl border bg-background p-5"
          aria-live="polite"
        >
          {state === "empty" && (
            <EmptyState
              title="A fresh start"
              description="When a feature has no records, explain what belongs here without inventing activity."
            />
          )}
          {state === "loading" && (
            <div role="status" className="space-y-4 p-5">
              <span className="sr-only">Loading preview</span>
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}
          {state === "error" && (
            <ErrorState
              title="Something interrupted the request"
              description="Preserve context and offer a clear way to retry. This is a simulated error."
              onRetry={() => setState("success")}
            />
          )}
          {state === "success" && (
            <div className="flex min-h-44 flex-col items-center justify-center text-center">
              <span className="rounded-full bg-emerald-100 p-3">
                <Check className="size-5 text-primary" />
              </span>
              <h3 className="mt-4 text-sm font-semibold">Ready to continue</h3>
              <p className="mt-2 text-xs text-muted-foreground">
                The preview completed successfully.
              </p>
            </div>
          )}
        </div>
      </Card>
      <p className="text-xs leading-6 text-muted-foreground">
        Components follow shadcn/ui conventions with local source ownership.
        Keyboard focus, semantic labels, reduced motion, and explicit state text
        are part of the foundation.
      </p>
    </div>
  );
}
