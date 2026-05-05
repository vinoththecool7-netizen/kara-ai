"use client";

import { useRef, useEffect, useCallback } from "react";
import { Menu } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { UseChatReturn } from "@/hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import { TypingIndicator } from "./TypingIndicator";
import { SuggestedQuestions } from "./SuggestedQuestions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ChatWindowProps {
  chat: UseChatReturn;
  /** Called when the user taps the mobile hamburger to open the sidebar. */
  onOpenSidebar: () => void;
  /** True while the mobile sidebar drawer is open — drives aria-expanded. */
  sidebarOpen: boolean;
}

export function ChatWindow({ chat, onOpenSidebar, sidebarOpen }: ChatWindowProps) {
  const {
    messages,
    isStreaming,
    isLoading,
    sendMessage,
    uploadAndProcess,
    retryMessage,
  } = chat;

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Track whether user is near the bottom of the scroll container
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    isNearBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  }, []);

  // Auto-scroll when messages change or streaming content appends
  useEffect(() => {
    if (!isNearBottomRef.current || !sentinelRef.current) return;
    const behavior = prefersReducedMotion() ? "instant" : "smooth";
    sentinelRef.current.scrollIntoView({ behavior });
  }, [messages, isStreaming]);

  // Determine whether to show the typing indicator:
  // streaming is active AND the last assistant message has no content yet
  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator =
    isStreaming && lastMessage?.role === "assistant" && lastMessage.content === "";

  const handleRetryMessage = useCallback(
    (id: string) => {
      void retryMessage(id);
    },
    [retryMessage],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Mobile-only header with hamburger to open the session sidebar */}
      <div className="md:hidden flex items-center px-2 py-2 border-b">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open session list"
          aria-controls="session-sidebar"
          aria-expanded={sidebarOpen}
          className={cn(
            "size-11 inline-flex items-center justify-center rounded-md",
            "text-foreground hover:bg-muted",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          )}
        >
          <Menu className="size-5" />
        </button>
      </div>

      {/* Messages area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
        role="log"
        aria-live="polite"
      >
        <div className="max-w-3xl mx-auto w-full px-4 py-8 space-y-6">
          {/* Loading skeleton — shown while restoring a session from localStorage */}
          {isLoading && (
            <div className="space-y-4 py-8" aria-label="Loading conversation history" aria-busy="true">
              {/* Skeleton bubble 1 — assistant, wide */}
              <div className="flex gap-3 items-start">
                <Skeleton className="size-8 rounded-full shrink-0" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </div>
              {/* Skeleton bubble 2 — user, right-aligned */}
              <div className="flex gap-3 items-start justify-end">
                <div className="space-y-2 flex-1 items-end flex flex-col">
                  <Skeleton className="h-4 w-2/5" />
                </div>
                <Skeleton className="size-8 rounded-full shrink-0" />
              </div>
              {/* Skeleton bubble 3 — assistant */}
              <div className="flex gap-3 items-start">
                <Skeleton className="size-8 rounded-full shrink-0" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-4 w-3/5" />
                  <Skeleton className="h-4 w-1/3" />
                </div>
              </div>
            </div>
          )}

          {messages.length === 0 && !isStreaming && !isLoading && (
            <div className="flex flex-col items-center justify-center gap-6 min-h-[60vh] py-8">
              {/* Avatar */}
              <Avatar
                className="size-16"
              >
                <AvatarFallback className="bg-kara-primary text-white text-2xl font-bold">
                  K
                </AvatarFallback>
              </Avatar>

              {/* Headings */}
              <div className="text-center space-y-1">
                <h2 className="text-2xl font-semibold tracking-tight">
                  Hi! I&#39;m Kara
                </h2>
                <p className="text-muted-foreground text-sm">
                  Your AI tax advisor for India
                </p>
              </div>

              {/* Suggestion chips */}
              <SuggestedQuestions onSelect={sendMessage} />
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onRetry={handleRetryMessage}
            />
          ))}

          {showTypingIndicator && <TypingIndicator />}

          {/* Scroll sentinel */}
          <div ref={sentinelRef} aria-hidden="true" />
        </div>
      </div>

      {/* Input area */}
      <MessageInput
        onSend={sendMessage}
        onFilesSelected={(files) => void uploadAndProcess(files)}
        disabled={isStreaming}
      />
    </div>
  );
}
