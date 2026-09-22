"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchCurrentUser, ApiError } from "@/lib/api";
import { User } from "@/types/job";

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCurrentUser();
      setUser(data);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        if (typeof window !== "undefined") {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = "/login";
        }
      }
      setError(err instanceof Error ? err.message : "Failed to load user profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetchCurrentUser()
      .then((data) => {
        if (active) {
          setUser(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          if (err instanceof ApiError && err.status === 401) {
            if (typeof window !== "undefined") {
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination
              window.location.href = "/login";
            }
          }
          setError(err instanceof Error ? err.message : "Failed to load user profile");
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

  const hasRole = useCallback(
    (role: string) => {
      return user?.roles?.includes(role) ?? false;
    },
    [user]
  );

  const isAdmin = hasRole("ADMIN");
  const isManager = hasRole("MANAGER");
  const isMember = hasRole("MEMBER");
  const canManageProjects = isAdmin || isManager;

  return {
    user,
    loading,
    error,
    refreshUser: loadUser,
    hasRole,
    isAdmin,
    isManager,
    isMember,
    canManageProjects,
  };
}
