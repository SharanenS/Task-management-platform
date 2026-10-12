"use client";
import { ErrorState } from "@/components/ui/states";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <ErrorState
      title="This page could not be loaded"
      description="Please try again. If the issue persists, restart the local development server."
      onRetry={reset}
    />
  );
}
