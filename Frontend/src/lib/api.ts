import { Job, JobStats, Project, JobCreatePayload, JobFilterParams } from "@/types/job";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (typeof window !== "undefined") {
    const savedToken = localStorage.getItem("task_platform_token");
    if (savedToken) {
      headers["Authorization"] = `Bearer ${savedToken}`;
    }
  }
  return headers;
}

export async function fetchJobStats(projectId?: string): Promise<JobStats> {
  const url = new URL(`${API_BASE_URL}/jobs/stats`);
  if (projectId) {
    url.searchParams.append("project_id", projectId);
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: getAuthHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch stats (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function fetchJobs(params: JobFilterParams = {}): Promise<Job[]> {
  const url = new URL(`${API_BASE_URL}/jobs`);
  if (params.project_id) url.searchParams.append("project_id", params.project_id);
  if (params.status) url.searchParams.append("status", params.status);
  if (params.job_type) url.searchParams.append("job_type", params.job_type.trim());
  if (params.skip !== undefined) url.searchParams.append("skip", String(params.skip));
  if (params.limit !== undefined) url.searchParams.append("limit", String(params.limit));

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: getAuthHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch jobs (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function fetchJobById(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: "GET",
    headers: getAuthHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch job (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function createJob(data: JobCreatePayload): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to create job (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function fetchProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE_URL}/projects?limit=100`, {
    method: "GET",
    headers: getAuthHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to fetch projects (${response.status}): ${errorText}`);
  }

  return response.json();
}
