"use client";

import { useState } from "react";
import { Trash2, Check, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/relative-time";
import type { SessionSummary } from "@/types/chat";

interface SessionListItemProps {
  session: SessionSummary;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

/**
 * One row in the session sidebar.
 *
 * Displays the derived title + relative timestamp + message count, with a
 * trash icon that swaps to an inline confirm/cancel pair when tapped.
 */
export function SessionListItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: SessionListItemProps) {
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 min-h-11 rounded-md",
          "bg-destructive/10 border border-destructive/30",
        )}
        role="group"
        aria-label="Confirm delete"
      >
        <span className="text-sm flex-1 truncate text-destructive">
          Delete this chat?
        </span>
        <button
          type="button"
          onClick={() => onDelete(session.id)}
          aria-label="Confirm delete"
          className={cn(
            "size-9 inline-flex items-center justify-center rounded",
            "text-destructive hover:bg-destructive/20",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40",
          )}
        >
          <Check className="size-4" />
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          aria-label="Cancel delete"
          className={cn(
            "size-9 inline-flex items-center justify-center rounded",
            "text-muted-foreground hover:bg-muted hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          )}
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="group relative">
      <button
        type="button"
        onClick={() => onSelect(session.id)}
        aria-current={isActive ? "true" : undefined}
        aria-label={`Open chat: ${session.title}`}
        className={cn(
          "w-full min-h-11 px-3 py-2 rounded-md text-left transition-colors",
          "flex flex-col gap-0.5 pr-11",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          isActive ? "bg-muted text-foreground" : "hover:bg-muted/60",
        )}
      >
        <span className="text-sm font-medium truncate">{session.title}</span>
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(session.updated_at)} · {session.message_count} msg
        </span>
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setConfirming(true);
        }}
        aria-label="Delete chat"
        className={cn(
          "absolute right-1.5 top-1/2 -translate-y-1/2",
          "size-9 inline-flex items-center justify-center rounded",
          "text-muted-foreground hover:text-destructive hover:bg-destructive/10",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40",
          // Hidden by default on desktop, shown on hover/focus.
          // Always visible on touch devices (no hover capability).
          "opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
          "transition-opacity duration-150",
          "[@media(hover:none)]:opacity-100",
        )}
      >
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}
