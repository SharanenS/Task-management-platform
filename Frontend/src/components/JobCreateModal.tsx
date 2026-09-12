"use client";

import React, { useState } from "react";
import { Project, JobCreatePayload } from "@/types/job";
import { createJob } from "@/lib/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  onJobCreated: () => void;
}

export const JobCreateModal: React.FC<Props> = ({
  isOpen,
  onClose,
  projects,
  onJobCreated,
}) => {
  const [projectId, setProjectId] = useState("");
  const [jobType, setJobType] = useState("REPORT_GENERATION");
  const [payloadText, setPayloadText] = useState('{\n  "report_type": "summary",\n  "format": "pdf"\n}');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const activeProject = projectId || (projects.length > 0 ? projects[0].id : "");
    if (!activeProject) {
      setError("Please select or create a project first.");
      return;
    }

    if (!jobType.trim()) {
      setError("Job type cannot be empty.");
      return;
    }

    let parsedPayload: Record<string, unknown> | undefined = undefined;
    if (payloadText.trim()) {
      try {
        parsedPayload = JSON.parse(payloadText);
      } catch (err: unknown) {
        setError(`Invalid JSON payload: ${err instanceof Error ? err.message : "Parse error"}`);
        return;
      }
    }

    try {
      setSubmitting(true);
      const data: JobCreatePayload = {
        project_id: activeProject,
        job_type: jobType.trim(),
        payload: parsedPayload,
      };

      await createJob(data);
      onJobCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
            </span>
            <h3 className="text-base font-bold text-slate-100">Dispatch Asynchronous Job</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300">
              {error}
            </div>
          )}

          {/* Project Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Target Project
            </label>
            <select
              value={projectId || (projects[0]?.id ?? "")}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {projects.length === 0 && <option value="">No projects available</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id.slice(0, 8)}...)
                </option>
              ))}
            </select>
          </div>

          {/* Job Type */}
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Job Type
            </label>
            <input
              type="text"
              value={jobType}
              onChange={(e) => setJobType(e.target.value)}
              placeholder="e.g. REPORT_GENERATION"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            />
            {/* Quick Presets */}
            <div className="flex gap-2 mt-2">
              {["REPORT_GENERATION", "DATA_SYNC", "NOTIFICATION_DISPATCH"].map((preset) => (
                <button
                  type="button"
                  key={preset}
                  onClick={() => setJobType(preset)}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Payload JSON */}
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-300 mb-1">
              Job Payload (JSON)
            </label>
            <textarea
              rows={5}
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 leading-relaxed"
            />
          </div>

          <div className="pt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 text-xs font-bold rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white shadow-lg shadow-indigo-500/25 transition disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
                  </svg>
                  <span>Dispatching...</span>
                </>
              ) : (
                "Enqueue Job"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
