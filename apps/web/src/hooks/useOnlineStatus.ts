"use client";

import { useSyncExternalStore } from "react";

type Listener = () => void;

const listeners = new Set<Listener>();
let recentFetchFailure = false;
let failureTimer: number | undefined;

// Snapshot must be reference-stable across calls when values are unchanged,
// otherwise useSyncExternalStore detects "changes" every render and loops.
let cachedSnapshot: OnlineStatus = { isOnline: true, hasRecentFailure: false };
const serverSnapshot: OnlineStatus = { isOnline: true, hasRecentFailure: false };

function getSnapshot(): OnlineStatus {
  const online = typeof navigator === "undefined" ? true : navigator.onLine;
  if (
    cachedSnapshot.isOnline !== online ||
    cachedSnapshot.hasRecentFailure !== recentFetchFailure
  ) {
    cachedSnapshot = { isOnline: online, hasRecentFailure: recentFetchFailure };
  }
  return cachedSnapshot;
}

function getServerSnapshot(): OnlineStatus {
  return serverSnapshot;
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  const handleOnline = () => {
    recentFetchFailure = false;
    emit();
  };
  const handleOffline = () => emit();
  if (typeof window !== "undefined") {
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
  }
  return () => {
    listeners.delete(listener);
    if (typeof window !== "undefined") {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    }
  };
}

function emit(): void {
  for (const l of listeners) l();
}

export interface OnlineStatus {
  isOnline: boolean;
  hasRecentFailure: boolean;
}

export function useOnlineStatus(): OnlineStatus {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Call from non-React code paths (fetch catches) to flag a failure. */
export function reportNetworkError(): void {
  recentFetchFailure = true;
  emit();
  if (typeof window !== "undefined") {
    if (failureTimer) window.clearTimeout(failureTimer);
    failureTimer = window.setTimeout(() => {
      recentFetchFailure = false;
      emit();
    }, 10000);
  }
}
