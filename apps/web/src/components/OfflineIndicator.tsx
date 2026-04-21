"use client";

import { useEffect, useRef } from "react";
import { WifiOff, RotateCcw } from "lucide-react";

import { useOnlineStatus } from "@/hooks/useOnlineStatus";
import { toast } from "@/hooks/useToast";
import { cn } from "@/lib/utils";

export function OfflineIndicator() {
  const { isOnline, hasRecentFailure } = useOnlineStatus();
  const wasOfflineRef = useRef(false);

  useEffect(() => {
    if (!isOnline) {
      wasOfflineRef.current = true;
    } else if (wasOfflineRef.current) {
      wasOfflineRef.current = false;
      toast.info("Back online");
    }
  }, [isOnline]);

  const visible = !isOnline || hasRecentFailure;
  if (!visible) return null;

  const label = !isOnline
    ? "You're offline. Messages can't be sent right now."
    : "Network trouble — some requests failed.";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "sticky top-0 z-50 w-full bg-destructive text-destructive-foreground",
        "px-4 py-2 text-sm flex items-center justify-center gap-3",
        "animate-in slide-in-from-top-2 duration-200 motion-reduce:animate-none",
      )}
    >
      <WifiOff className="size-4 shrink-0" aria-hidden="true" />
      <span>{label}</span>
      <button
        type="button"
        onClick={() => {
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("kara:retry"));
          }
        }}
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5",
          "hover:bg-white/10",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40",
        )}
      >
        <RotateCcw className="size-3.5" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}
