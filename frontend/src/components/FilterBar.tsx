"use client";

import React from "react";
import { JobStatus, Project } from "@/types/job";

interface Props {
  projects: Project[];
  selectedProjectId: string;
  onSelectProject: (id: string) => void;
  selectedStatus: JobStatus | "";
  onSelectStatus: (status: JobStatus | "") => void;
  jobTypeSearch: string;
  onJobTypeSearch: (type: string) => void;
  pollingInterval: number;
  onSelectPolling: (ms: number) => void;
  onManualRefresh: () => void;
  isRefreshing: boolean;
  onOpenCreateModal: () => void;
}

export const FilterBar: React.FC<Props> = ({
  projects,
  selectedProjectId,
  onSelectProject,
  selectedStatus,
  onSelectStatus,
  jobTypeSearch,
  onJobTypeSearch,
  pollingInterval,
  onSelectPolling,
  onManualRefresh,
  isRefreshing,
  onOpenCreateModal,
}) => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md flex flex-col lg:flex-row gap-4 justify-between items-stretch lg:items-center">
      {/* Left controls: Project & Job Type */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Project Selector */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold uppercase text-slate-400">Project:</label>
          <select
            value={selectedProjectId}
            onChange={(e) => onSelectProject(e.target.value)}
            className="bg-slate-800/90 text-slate-200 border border-slate-700/80 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Job Type Input Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Filter by Job Type..."
            value={jobTypeSearch}
            onChange={(e) => onJobTypeSearch(e.target.value)}
            className="bg-slate-800/90 text-slate-200 border border-slate-700/80 text-sm rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-48 lg:w-56"
          />
          <svg
            className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        {/* Clear filters shortcut */}
        {(selectedProjectId || selectedStatus || jobTypeSearch) && (
          <button
            onClick={() => {
              onSelectProject("");
              onSelectStatus("");
              onJobTypeSearch("");
            }}
            className="text-xs text-indigo-400 hover:text-indigo-300 underline underline-offset-2 ml-1"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Right controls: Polling, Refresh, Trigger Job */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Polling Selector */}
        <div className="flex items-center gap-1.5 bg-slate-800/60 border border-slate-700/60 rounded-lg px-2 py-1 text-xs text-slate-300">
          <span
            className={`w-2 h-2 rounded-full ${
              pollingInterval > 0 ? "bg-emerald-400 animate-pulse" : "bg-slate-600"
            }`}
          ></span>
          <span className="font-medium">Auto-Refresh:</span>
          <select
            value={pollingInterval}
            onChange={(e) => onSelectPolling(Number(e.target.value))}
            className="bg-transparent text-slate-200 font-semibold focus:outline-none cursor-pointer"
          >
            <option value={0} className="bg-slate-800">Off</option>
            <option value={3000} className="bg-slate-800">3s</option>
            <option value={5000} className="bg-slate-800">5s</option>
            <option value={10000} className="bg-slate-800">10s</option>
          </select>
        </div>

        {/* Manual Refresh Button */}
        <button
          onClick={onManualRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 border border-slate-700 transition active:scale-95 disabled:opacity-50"
          title="Refresh now"
        >
          <svg
            className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-indigo-400" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Refresh
        </button>

        {/* Trigger Job Action Button */}
        <button
          onClick={onOpenCreateModal}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white shadow-md hover:shadow-indigo-500/25 transition active:scale-95"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Dispatch Job
        </button>
      </div>
    </div>
  );
};
