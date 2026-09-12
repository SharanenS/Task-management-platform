export type JobStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface Job {
  id: string;
  project_id: string;
  job_type: string;
  status: JobStatus;
  payload: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobStats {
  total_count: number;
  queued_count: number;
  processing_count: number;
  completed_count: number;
  failed_count: number;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobCreatePayload {
  project_id: string;
  job_type: string;
  payload?: Record<string, unknown>;
}

export interface JobFilterParams {
  project_id?: string;
  status?: JobStatus | "";
  job_type?: string;
  skip?: number;
  limit?: number;
}
