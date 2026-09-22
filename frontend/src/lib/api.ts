import {
  Job,
  JobStats,
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  JobCreatePayload,
  JobFilterParams,
  User,
} from "@/types/job";

const API_BASE_URL = "/api/backend/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const UNAUTHORIZED_EVENT = "task_platform_unauthorized";

function handleResponseError(status: number, errorText: string, contextMessage: string): never {
  if (status === 401) {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
  }
  throw new ApiError(`${contextMessage} (${status}): ${errorText}`, status);
}

function getDefaultHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
  };
}

export async function fetchCurrentUser(): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "GET",
    headers: getDefaultHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to fetch current user");
  }

  return response.json();
}

export async function fetchJobStats(projectId?: string): Promise<JobStats> {
  const url = new URL(`${API_BASE_URL}/jobs/stats`, "http://localhost:3000");
  if (projectId) {
    url.searchParams.append("project_id", projectId);
  }

  const response = await fetch(`${url.pathname}${url.search}`, {
    method: "GET",
    headers: getDefaultHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to fetch stats");
  }

  return response.json();
}

export async function fetchJobs(params: JobFilterParams = {}): Promise<Job[]> {
  const url = new URL(`${API_BASE_URL}/jobs`, "http://localhost:3000");
  if (params.project_id) url.searchParams.append("project_id", params.project_id);
  if (params.status) url.searchParams.append("status", params.status);
  if (params.job_type) url.searchParams.append("job_type", params.job_type.trim());
  if (params.skip !== undefined) url.searchParams.append("skip", String(params.skip));
  if (params.limit !== undefined) url.searchParams.append("limit", String(params.limit));

  const response = await fetch(`${url.pathname}${url.search}`, {
    method: "GET",
    headers: getDefaultHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to fetch jobs");
  }

  return response.json();
}

export async function fetchJobById(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: "GET",
    headers: getDefaultHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to fetch job");
  }

  return response.json();
}

export async function createJob(data: JobCreatePayload): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: getDefaultHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to create job");
  }

  return response.json();
}

export async function fetchProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE_URL}/projects?limit=100`, {
    method: "GET",
    headers: getDefaultHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to fetch projects");
  }

  return response.json();
}

export async function createProject(data: ProjectCreatePayload): Promise<Project> {
  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: "POST",
    headers: getDefaultHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to create project");
  }

  return response.json();
}

export async function updateProject(
  id: string,
  data: ProjectUpdatePayload
): Promise<Project> {
  const response = await fetch(`${API_BASE_URL}/projects/${id}`, {
    method: "PATCH",
    headers: getDefaultHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to update project");
  }

  return response.json();
}

export async function deleteProject(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${id}`, {
    method: "DELETE",
    headers: getDefaultHeaders(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    handleResponseError(response.status, errorText, "Failed to delete project");
  }
}
