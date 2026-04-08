"use client";

import { useCallback, useEffect, useState } from "react";
import { listSessions, deleteSession } from "@/lib/api";
import type { SessionSummary } from "@/types/chat";

export interface UseSessionsReturn {
  sessions: SessionSummary[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  removeSession: (id: string) => Promise<void>;
}

/**
 * Manages the list of chat sessions shown in the sidebar.
 *
 * Fetches once on mount and exposes:
 *   - `refetch()` to reload (called after a new session is created)
 *   - `removeSession(id)` for optimistic delete with rollback on failure
 */
export function useSessions(): UseSessionsReturn {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load sessions",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const removeSession = useCallback(
    async (id: string): Promise<void> => {
      // Snapshot the current list for rollback if the request fails
      let previous: SessionSummary[] = [];
      setSessions((current) => {
        previous = current;
        return current.filter((s) => s.id !== id);
      });
      try {
        await deleteSession(id);
      } catch (err) {
        // Roll back optimistic removal
        setSessions(previous);
        throw err;
      }
    },
    [],
  );

  return { sessions, isLoading, error, refetch, removeSession };
}
