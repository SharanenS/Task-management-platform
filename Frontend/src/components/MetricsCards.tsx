"use client";

import React from "react";
import { JobStats, JobStatus } from "@/types/job";

interface Props {
  stats: JobStats | null;
  loading: boolean;
  selectedStatus?: JobStatus | "";
  onSelectStatus: (status: JobStatus | "") => void;
}

export const MetricsCards: React.FC<Props> = ({
  stats,
  loading,
  selectedStatus,
  onSelectStatus,
}) => {
  const cards = [
    {
      label: "Total Workflows",
      count: stats?.total_count ?? 0,
      status: "" as const,
      color: "from-blue-500/20 to-indigo-500/10 border-blue-500/30 text-blue-400",
      accent: "text-slate-100",
      icon: (
        <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
    },
    {
      label: "Queued",
      count: stats?.queued_count ?? 0,
      status: "QUEUED" as const,
      color: "from-amber-500/20 to-yellow-500/10 border-amber-500/30 text-amber-400",
      accent: "text-amber-300",
      icon: (
        <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      label: "Processing",
      count: stats?.processing_count ?? 0,
      status: "PROCESSING" as const,
      color: "from-cyan-500/20 to-sky-500/10 border-cyan-500/30 text-cyan-400",
      accent: "text-cyan-300",
      icon: (
        <svg className="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      ),
    },
    {
      label: "Completed",
      count: stats?.completed_count ?? 0,
      status: "COMPLETED" as const,
      color: "from-emerald-500/20 to-green-500/10 border-emerald-500/30 text-emerald-400",
      accent: "text-emerald-300",
      icon: (
        <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      label: "Failed",
      count: stats?.failed_count ?? 0,
      status: "FAILED" as const,
      color: "from-rose-500/20 to-red-500/10 border-rose-500/30 text-rose-400",
      accent: "text-rose-300",
      icon: (
        <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map((c) => {
        const isSelected = selectedStatus === c.status;
        return (
          <button
            key={c.label}
            onClick={() => onSelectStatus(c.status)}
            className={`text-left relative overflow-hidden rounded-xl border p-4 transition-all duration-200 bg-gradient-to-br bg-slate-900/60 backdrop-blur-sm cursor-pointer group ${
              c.color
            } ${
              isSelected
                ? "ring-2 ring-indigo-400 ring-offset-2 ring-offset-slate-950 scale-[1.02] shadow-lg"
                : "hover:border-slate-600 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 group-hover:text-slate-200">
                {c.label}
              </span>
              <div className="p-2 rounded-lg bg-slate-800/80 group-hover:scale-110 transition-transform">
                {c.icon}
              </div>
            </div>

            <div className="mt-3">
              {loading && !stats ? (
                <div className="h-8 w-16 bg-slate-800 animate-pulse rounded"></div>
              ) : (
                <div className={`text-2xl md:text-3xl font-bold tracking-tight ${c.accent}`}>
                  {c.count.toLocaleString()}
                </div>
              )}
            </div>

            {stats && stats.total_count > 0 && c.status !== "" && (
              <div className="mt-2 text-[11px] text-slate-400">
                {((c.count / stats.total_count) * 100).toFixed(1)}% of total
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
};
