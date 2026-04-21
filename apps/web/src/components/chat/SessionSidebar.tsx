"use client";

import { useEffect } from "react";
import { Plus, MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/types/chat";
import { SessionListItem } from "./SessionListItem";

interface SessionSidebarProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onRetry: () => void;
  /** Mobile drawer open state. Ignored on desktop (always visible). */
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Persistent left rail on desktop (>=md) and slide-in drawer on mobile.
 *
 * - Desktop (>=md): always visible, 280px wide, no backdrop
 * - Mobile (<md): hidden offscreen, slides in via translate, dim backdrop
 *
 * Escape closes the drawer; tapping the backdrop also closes it.
 */
export function SessionSidebar({
  sessions,
  currentSessionId,
  isLoading,
  error,
  onSelect,
  onNewChat,
  onDelete,
  onRetry,
  isOpen,
  onClose,
}: SessionSidebarProps) {
  // Escape-to-close (mobile only — desktop sidebar can't be closed)
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Mobile backdrop — only rendered when drawer is open */}
      {isOpen && (
        <div
          onClick={onClose}
          aria-hidden="true"
          className={cn(
            "md:hidden fixed inset-0 bg-black/50 z-40",
            "animate-in fade-in duration-200 motion-reduce:animate-none",
          )}
        />
      )}

      <aside
        id="session-sidebar"
        role="navigation"
        aria-label="Chat sessions"
        className={cn(
          "bg-background border-r flex flex-col",
          // Desktop layout
          "md:static md:translate-x-0 md:z-auto md:w-[280px] md:h-full",
          // Mobile drawer
          "fixed inset-y-0 left-0 w-72 z-50",
          "transition-transform duration-200 ease-out motion-reduce:transition-none",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        {/* Header — New Chat button */}
        <div className="p-3 border-b">
          <Button
            type="button"
            onClick={onNewChat}
            className="w-full min-h-11"
            aria-label="Start new chat (Ctrl+Shift+N)"
          >
            <Plus className="size-4 mr-2" aria-hidden="true" />
            New Chat
          </Button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {isLoading && (
            <div className="space-y-2" aria-busy="true" aria-label="Loading sessions">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 bg-muted/50" />
              ))}
            </div>
          )}

          {error && !isLoading && (
            <div role="alert" className="p-4 text-center">
              <p className="text-sm text-destructive mb-2">
                Failed to load sessions
              </p>
              <Button variant="outline" size="sm" onClick={onRetry}>
                Retry
              </Button>
            </div>
          )}

          {!isLoading && !error && sessions.length === 0 && (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <MessageSquare
                className="size-8 mx-auto mb-2 opacity-50"
                aria-hidden="true"
              />
              <p>No past chats yet.</p>
              <p>Start a conversation!</p>
            </div>
          )}

          {!isLoading && !error &&
            sessions.map((session) => (
              <SessionListItem
                key={session.id}
                session={session}
                isActive={session.id === currentSessionId}
                onSelect={(id) => {
                  onSelect(id);
                  onClose(); // close drawer on mobile
                }}
                onDelete={onDelete}
              />
            ))}
        </div>
      </aside>
    </>
  );
}
