"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@/hooks/useUser";

export function NavBar() {
  const pathname = usePathname();
  const { user, loading } = useUser();

  const isJobs = pathname === "/";
  const isProjects = pathname.startsWith("/projects");

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case "ADMIN":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "MANAGER":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "MEMBER":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      default:
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#090d16]/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Branding & Navigation Links */}
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform duration-200">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.2"
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
                TaskPlatform
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 hidden sm:inline-block">
                  Enterprise
                </span>
              </span>
            </div>
          </Link>

          {/* Navigation Items */}
          <nav className="flex items-center gap-1">
            <Link
              href="/"
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isJobs
                  ? "bg-slate-800 text-white shadow-sm border border-slate-700/60"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Jobs Dashboard
            </Link>
            <Link
              href="/projects"
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isProjects
                  ? "bg-slate-800 text-white shadow-sm border border-slate-700/60"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              Projects
            </Link>
          </nav>
        </div>

        {/* Right: User profile badge & Logout */}
        <div className="flex items-center gap-3">
          {loading ? (
            <div className="h-8 w-32 bg-slate-800/50 rounded-lg animate-pulse" />
          ) : user ? (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-[10px] font-bold text-white uppercase shadow-sm">
                  {user.preferred_username?.charAt(0) || "U"}
                </div>
                <span className="font-medium text-slate-200">
                  {user.preferred_username || user.sub}
                </span>

                {user.roles && user.roles.length > 0 && (
                  <div className="flex items-center gap-1 ml-1">
                    {user.roles.map((role) => (
                      <span
                        key={role}
                        className={`text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded border ${getRoleBadgeColor(
                          role
                        )}`}
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Logout button */}
              <form action="/logout" method="POST">
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all flex items-center gap-1.5"
                  title="Sign out of Enterprise Task Platform"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                    />
                  </svg>
                  <span>Logout</span>
                </button>
              </form>
            </div>
          ) : (
            <Link
              href="/login"
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white shadow transition-all"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
