import { Suspense } from "react";
import { JobDirectory } from "@/features/jobs/job-directory";

export default function JobsPage() {
  return (
    <Suspense>
      <JobDirectory />
    </Suspense>
  );
}
