"use client";

import React, { useState } from "react";
import { Job, Project } from "@/types/job";
import { JobStatusBadge } from "./JobStatusBadge";

interface Props {
  job: Job | null;
  onClose: () => void;
  projects: Project[];
}

export const JobDetailModal: React.FC<Props> = ({ job, onClose, projects }) => {
  const [copied, setCopied] = useState(false);

  if (!job) return null;

  const projectMap = new Map(projects.map((p) => [p.id, p.name]));
  const projectName = projectMap.get(job.project_id) || "Unknown Project";

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(job, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const calculateDuration = () => {
    if (!job.created_at || !job.updated_at) return "-";
    const start = new Date(job.created_at).getTime();
    const end = new Date(job.updated_at).getTime();
    const diffMs = Math.max(0, end - start);
    if (diffMs < 1000) return `${diffMs}ms`;
    return `${(diffMs / 1000).toFixed(2)}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <JobStatusBadge status={job.status} />
            <span className="text-sm font-bold text-slate-100 font-mono">
              Job: {job.id.slice(0, 13)}...
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="p-1.5 text-xs text-slate-400 hover:text-indigo-400 rounded-md bg-slate-800 hover:bg-slate-750 transition"
              title="Copy Raw JSON"
            >
              {copied ? (
                <span className="text-emerald-400 text-xs px-1">Copied!</span>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Failure Alert Banner */}
          {job.status === "FAILED" && job.error_message && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300">
              <div className="flex items-center gap-2 font-semibold text-sm mb-1">
                <svg className="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>Execution Error</span>
              </div>
              <pre className="text-xs font-mono whitespace-pre-wrap bg-rose-950/40 p-2.5 rounded border border-rose-900/50">
                {job.error_message}
              </pre>
            </div>
          )}

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <span className="text-[10px] font-semibold text-slate-400 uppercase">Job Type</span>
              <p className="text-xs font-bold text-slate-200 mt-1 font-mono">{job.job_type}</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <span className="text-[10px] font-semibold text-slate-400 uppercase">Project</span>
              <p className="text-xs font-bold text-slate-200 mt-1 truncate" title={job.project_id}>
                {projectName}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <span className="text-[10px] font-semibold text-slate-400 uppercase">Duration</span>
              <p className="text-xs font-bold text-slate-200 mt-1 font-mono">{calculateDuration()}</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <span className="text-[10px] font-semibold text-slate-400 uppercase">Status</span>
              <p className="text-xs font-bold text-slate-200 mt-1 font-mono">{job.status}</p>
            </div>
          </div>

          {/* Detailed IDs */}
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Full Job ID</span>
              <span className="font-mono text-slate-300 select-all">{job.id}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Project ID</span>
              <span className="font-mono text-slate-300 select-all">{job.project_id}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Created At</span>
              <span className="font-mono text-slate-300">{job.created_at}</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Updated At</span>
              <span className="font-mono text-slate-300">{job.updated_at}</span>
            </div>
          </div>

          {/* Payload JSON Inspector */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold uppercase text-slate-300">
                Payload Parameters
              </span>
              <span className="text-[10px] text-slate-400">JSON Object</span>
            </div>
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 overflow-x-auto">
              <pre className="text-xs font-mono text-slate-300">
                {job.payload ? JSON.stringify(job.payload, null, 2) : "// No payload provided"}
              </pre>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-slate-800/80 border-t border-slate-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
