"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Project, ProjectStatus, ProjectCreatePayload } from "@/types/job";
import { fetchProjects, createProject, updateProject, deleteProject } from "@/lib/api";
import { useUser } from "@/hooks/useUser";

const STATUS_COLORS: Record<ProjectStatus, string> = {
  PLANNING: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  ACTIVE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  COMPLETED: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  ARCHIVED: "bg-slate-500/10 text-slate-400 border-slate-500/30",
};

const ALL_STATUSES: ProjectStatus[] = ["PLANNING", "ACTIVE", "COMPLETED", "ARCHIVED"];

export default function ProjectsPage() {
  const { user, isAdmin, canManageProjects } = useUser();

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newStatus, setNewStatus] = useState<ProjectStatus>("PLANNING");

  // Deletion modal state
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Updating status in-flight
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadProjects = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await fetchProjects();
      setProjects(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetchProjects()
      .then((data) => {
        if (active) {
          setProjects(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load projects");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    try {
      setCreating(true);
      setActionError(null);
      const payload: ProjectCreatePayload = {
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        status: newStatus,
      };
      await createProject(payload);
      setIsCreateOpen(false);
      setNewName("");
      setNewDescription("");
      setNewStatus("PLANNING");
      setActionSuccess("Project created successfully");
      setTimeout(() => setActionSuccess(null), 4000);
      await loadProjects();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = async (projectId: string, nextStatus: ProjectStatus) => {
    try {
      setUpdatingId(projectId);
      setActionError(null);
      await updateProject(projectId, { status: nextStatus });
      setProjects((prev) =>
        prev.map((p) => (p.id === projectId ? { ...p, status: nextStatus } : p))
      );
      setActionSuccess("Project status updated");
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async () => {
    if (!projectToDelete) return;
    try {
      setDeleting(true);
      setActionError(null);
      await deleteProject(projectToDelete.id);
      setProjectToDelete(null);
      setActionSuccess("Project deleted successfully");
      setTimeout(() => setActionSuccess(null), 3000);
      await loadProjects();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100">
      {/* Subheader */}
      <div className="border-b border-slate-800/60 bg-slate-900/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2.5">
              Projects Management
              <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                Workspace
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Organize workflows, track lifecycle statuses, and manage role permissions
            </p>
          </div>

          <div className="flex items-center gap-3">
            {canManageProjects ? (
              <button
                onClick={() => setIsCreateOpen(true)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2 cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 4v16m8-8H4" />
                </svg>
                <span>Create Project</span>
              </button>
            ) : (
              <div
                className="px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-400"
                title="Only ADMIN or MANAGER roles can create projects"
              >
                Viewing as Member (Read Only)
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Banner messages */}
        {actionSuccess && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2.5">
            <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
            <span>{actionSuccess}</span>
          </div>
        )}

        {actionError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
            <svg className="w-4 h-4 text-rose-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{actionError}</span>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3 shadow-lg">
            <svg className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1 text-xs">
              <p className="font-semibold text-rose-200">Unable to load projects</p>
              <p className="mt-0.5 text-rose-300/90">{error}</p>
            </div>
            <button
              onClick={() => loadProjects(true)}
              className="px-2.5 py-1 text-xs bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 rounded-md transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Projects Grid / List */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-48 rounded-2xl bg-slate-900/60 border border-slate-800 p-6 animate-pulse flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="h-5 w-2/3 bg-slate-800 rounded" />
                  <div className="h-3 w-full bg-slate-800/60 rounded" />
                  <div className="h-3 w-4/5 bg-slate-800/60 rounded" />
                </div>
                <div className="h-4 w-1/3 bg-slate-800 rounded" />
              </div>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center bg-slate-900/20">
            <div className="w-12 h-12 mx-auto rounded-xl bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-white">No projects found</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              Get started by creating your first enterprise workflow project to group jobs and tasks.
            </p>
            {canManageProjects && (
              <button
                onClick={() => setIsCreateOpen(true)}
                className="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition shadow"
              >
                Create First Project
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((project) => {
              const statusColor = STATUS_COLORS[project.status] || "bg-slate-800 text-slate-400 border-slate-700";
              const isUpdating = updatingId === project.id;

              return (
                <div
                  key={project.id}
                  className="rounded-2xl bg-slate-900/70 border border-slate-800/80 p-5 hover:border-slate-700 transition-all flex flex-col justify-between group shadow-lg shadow-black/20"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-bold text-white group-hover:text-indigo-300 transition-colors line-clamp-1">
                        {project.name}
                      </h3>

                      {/* Status Selector or Static Badge */}
                      {canManageProjects ? (
                        <div className="relative">
                          <select
                            disabled={isUpdating}
                            value={project.status}
                            onChange={(e) =>
                              handleStatusChange(project.id, e.target.value as ProjectStatus)
                            }
                            className={`text-[10px] uppercase font-bold px-2 py-1 rounded-lg border appearance-none pr-6 cursor-pointer bg-transparent transition ${statusColor} ${
                              isUpdating ? "opacity-50 cursor-wait" : ""
                            }`}
                          >
                            {ALL_STATUSES.map((st) => (
                              <option key={st} value={st} className="bg-slate-900 text-slate-200">
                                {st}
                              </option>
                            ))}
                          </select>
                          <div className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-current opacity-70">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </div>
                      ) : (
                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-md border ${statusColor}`}>
                          {project.status}
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2 min-h-[2rem]">
                      {project.description || (
                        <span className="italic text-slate-500">No description provided</span>
                      )}
                    </p>
                  </div>

                  {/* Card Footer: Metadata & Actions */}
                  <div className="mt-5 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                    <div className="truncate max-w-[170px]" title={`Owner: ${project.owner_id}`}>
                      <span className="text-slate-500">Owner:</span>{" "}
                      <span className="font-mono text-slate-300">{project.owner_id}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-slate-500">
                        {new Date(project.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>

                      {/* Admin Delete Action */}
                      {isAdmin && (
                        <button
                          onClick={() => setProjectToDelete(project)}
                          className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-md transition"
                          title="Delete Project (Admin Only)"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Create Project Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>Create New Project</span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {user?.roles?.join(", ") || "Authorized"}
                </span>
              </h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-white transition"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Project Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Data Analytics Pipeline"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-slate-100 text-xs placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Description <span className="text-slate-500">(optional)</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="Brief description of the workflow or project scope"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-slate-100 text-xs placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Initial Status
                </label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as ProjectStatus)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-indigo-500 transition"
                >
                  {ALL_STATUSES.map((st) => (
                    <option key={st} value={st}>
                      {st}
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition shadow disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creating ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {projectToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>

            <div>
              <h3 className="text-sm font-bold text-white">Delete Project?</h3>
              <p className="text-xs text-slate-400 mt-1">
                Are you sure you want to delete{" "}
                <span className="font-semibold text-slate-200">
                  {projectToDelete.name}
                </span>
                ? This action cannot be undone.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setProjectToDelete(null)}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={handleDelete}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition shadow disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete Permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
