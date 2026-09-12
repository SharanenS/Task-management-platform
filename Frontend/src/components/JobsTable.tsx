"use client";

import React, { useState } from "react";
import { Job, Project } from "@/types/job";
import { JobStatusBadge } from "./JobStatusBadge";

interface Props {
  jobs: Job[];
  projects: Project[];
  loading: boolean;
  onSelectJob: (job: Job) => void;
  page: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
}

export const JobsTable: React.FC<Props> = ({
  jobs,
  projects,
  loading,
  onSelectJob,
  page,
  pageSize,
  onPageChange,
}) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const projectMap = new Map(projects.map((p) => [p.id, p.name]));

  const handleCopy = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) +
        " (" + d.toLocaleDateString() + ")";
    } catch {
      return iso;
    }
  };

  const calculateDuration = (job: Job) => {
    if (!job.created_at || !job.updated_at) return "-";
    const start = new Date(job.created_at).getTime();
    const end = new Date(job.updated_at).getTime();
    const diffMs = Math.max(0, end - start);
    if (job.status === "QUEUED") return "Awaiting claim";
    if (diffMs < 1000) return `${diffMs}ms`;
    return `${(diffMs / 1000).toFixed(2)}s`;
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl backdrop-blur-md overflow-hidden flex flex-col">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-800/80 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-700/80">
            <tr>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Job ID</th>
              <th className="py-3 px-4">Job Type</th>
              <th className="py-3 px-4">Project</th>
              <th className="py-3 px-4">Duration</th>
              <th className="py-3 px-4">Created</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {loading && jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-500">
                  <div className="inline-flex items-center gap-2">
                    <svg
                      className="animate-spin h-5 w-5 text-indigo-400"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                      ></path>
                    </svg>
                    <span>Loading distributed job events...</span>
                  </div>
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <svg className="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                    <p className="text-sm">No jobs found matching the active criteria.</p>
                  </div>
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => onSelectJob(job)}
                  className="hover:bg-slate-800/50 transition duration-150 cursor-pointer group"
                >
                  <td className="py-3 px-4 whitespace-nowrap">
                    <JobStatusBadge status={job.status} />
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-1.5 font-mono text-xs text-slate-300">
                      <span>{job.id.slice(0, 8)}...</span>
                      <button
                        onClick={(e) => handleCopy(job.id, e)}
                        className="text-slate-500 hover:text-indigo-400 p-1 rounded transition"
                        title="Copy full UUID"
                      >
                        {copiedId === job.id ? (
                          <span className="text-[10px] text-emerald-400 font-sans font-semibold">Copied!</span>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap font-medium text-slate-200">
                    <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-xs font-mono">
                      {job.job_type}
                    </span>
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap text-xs text-slate-400">
                    {projectMap.get(job.project_id) || `${job.project_id.slice(0, 8)}...`}
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap text-xs font-mono text-slate-400">
                    {calculateDuration(job)}
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap text-xs text-slate-400">
                    {formatTimestamp(job.created_at)}
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectJob(job);
                      }}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-indigo-400 hover:text-white bg-indigo-500/10 hover:bg-indigo-600 rounded-md transition"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      Inspect
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="bg-slate-800/40 border-t border-slate-800 px-4 py-3 flex items-center justify-between">
        <span className="text-xs text-slate-400">
          Page <span className="font-semibold text-slate-200">{page}</span> (Limit: {pageSize})
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1 || loading}
            className="px-2.5 py-1 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 transition"
          >
            Previous
          </button>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={jobs.length < pageSize || loading}
            className="px-2.5 py-1 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 transition"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
