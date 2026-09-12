"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Job, JobStats, Project, JobStatus } from "@/types/job";
import { fetchJobs, fetchJobStats, fetchProjects } from "@/lib/api";
import { MetricsCards } from "@/components/MetricsCards";
import { FilterBar } from "@/components/FilterBar";
import { JobsTable } from "@/components/JobsTable";
import { JobCreateModal } from "@/components/JobCreateModal";
import { JobDetailModal } from "@/components/JobDetailModal";

export default function DashboardPage() {
  const [stats, setStats] = useState<JobStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  // Filters & Pagination
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<JobStatus | "">("");
  const [jobTypeSearch, setJobTypeSearch] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const pageSize = 25;

  // Polling & Refresh
  const [pollingInterval, setPollingInterval] = useState<number>(5000);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [createModalOpen, setCreateModalOpen] = useState<boolean>(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // Load Projects once
  useEffect(() => {
    fetchProjects()
      .then((p) => setProjects(p))
      .catch((err) => {
        console.warn("Could not load projects (demo fallback):", err);
      });
  }, []);

  // Main data loader
  const loadData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    setError(null);

    try {
      const [statsData, jobsData] = await Promise.all([
        fetchJobStats(selectedProjectId || undefined),
        fetchJobs({
          project_id: selectedProjectId || undefined,
          status: selectedStatus || undefined,
          job_type: jobTypeSearch || undefined,
          skip: (page - 1) * pageSize,
          limit: pageSize,
        }),
      ]);

      setStats(statsData);
      setJobs(jobsData);
    } catch (err: unknown) {
      console.error("Dashboard fetch error:", err);
      setError(err instanceof Error ? err.message : "Failed to communicate with the task platform API");
    } finally {
      setLoading(false);
      if (showRefreshing) setIsRefreshing(false);
    }
  }, [selectedProjectId, selectedStatus, jobTypeSearch, page, pageSize]);

  // Initial load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Polling effect
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (pollingInterval <= 0) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      return;
    }

    pollTimerRef.current = setInterval(() => {
      loadData();
    }, pollingInterval);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [pollingInterval, loadData]);

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                Enterprise Task Platform
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                  Phase 9 Dashboard
                </span>
              </h1>
              <p className="text-xs text-slate-400 hidden sm:block">
                Transactional Outbox & Celery Worker Orchestration
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-lg bg-slate-800/80 border border-slate-700/80 text-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-slate-300 font-medium">System Active</span>
              <span className="text-slate-500">|</span>
              <span className="text-indigo-400 font-mono">PostgreSQL + RabbitMQ</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Error Alert if API is down */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3 shadow-lg">
            <svg className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1 text-xs">
              <p className="font-semibold text-rose-200">API Connection Notice</p>
              <p className="mt-0.5 text-rose-300/90">{error}</p>
              <p className="mt-2 text-[11px] text-rose-400/80">
                Make sure the backend is running at <code className="bg-rose-950/60 px-1 py-0.5 rounded">http://localhost:8000</code>.
              </p>
            </div>
            <button
              onClick={() => loadData(true)}
              className="px-2.5 py-1 text-xs bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 rounded-md transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* KPI Metrics Row */}
        <section aria-label="Job Statistics">
          <MetricsCards
            stats={stats}
            loading={loading}
            selectedStatus={selectedStatus}
            onSelectStatus={(st) => {
              setSelectedStatus(st);
              setPage(1);
            }}
          />
        </section>

        {/* Filter & Control Bar */}
        <section aria-label="Filters and Actions">
          <FilterBar
            projects={projects}
            selectedProjectId={selectedProjectId}
            onSelectProject={(p) => {
              setSelectedProjectId(p);
              setPage(1);
            }}
            selectedStatus={selectedStatus}
            onSelectStatus={(s) => {
              setSelectedStatus(s);
              setPage(1);
            }}
            jobTypeSearch={jobTypeSearch}
            onJobTypeSearch={(t) => {
              setJobTypeSearch(t);
              setPage(1);
            }}
            pollingInterval={pollingInterval}
            onSelectPolling={setPollingInterval}
            onManualRefresh={() => loadData(true)}
            isRefreshing={isRefreshing}
            onOpenCreateModal={() => setCreateModalOpen(true)}
          />
        </section>

        {/* Jobs Table */}
        <section aria-label="Jobs List">
          <JobsTable
            jobs={jobs}
            projects={projects}
            loading={loading}
            onSelectJob={setSelectedJob}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </section>
      </main>

      {/* Modals */}
      <JobCreateModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        projects={projects}
        onJobCreated={() => loadData(true)}
      />

      <JobDetailModal
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        projects={projects}
      />
    </div>
  );
}
