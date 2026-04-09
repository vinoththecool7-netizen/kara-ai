"use client";

import { useRef, useEffect, useCallback } from "react";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
}

export function ChatWindow({ chat, onOpenSidebar }: ChatWindowProps) {
  const {
    messages,
    isStreaming,
    isLoading,
    error,
    sendMessage,
    dismissError,
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
                <div className="size-8 rounded-full bg-muted animate-pulse shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-muted animate-pulse rounded-md w-3/4" />
                  <div className="h-4 bg-muted animate-pulse rounded-md w-1/2" />
                </div>
              </div>
              {/* Skeleton bubble 2 — user, right-aligned */}
              <div className="flex gap-3 items-start justify-end">
                <div className="space-y-2 flex-1 items-end flex flex-col">
                  <div className="h-4 bg-muted animate-pulse rounded-md w-2/5" />
                </div>
                <div className="size-8 rounded-full bg-muted animate-pulse shrink-0" />
              </div>
              {/* Skeleton bubble 3 — assistant */}
              <div className="flex gap-3 items-start">
                <div className="size-8 rounded-full bg-muted animate-pulse shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-muted animate-pulse rounded-md w-4/5" />
                  <div className="h-4 bg-muted animate-pulse rounded-md w-3/5" />
                  <div className="h-4 bg-muted animate-pulse rounded-md w-1/3" />
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

          {/* Error banner — inline retry lives on the failed user bubble;
              the banner just surfaces the error text with a dismiss affordance. */}
          {error && (
            <div
              className={cn(
                "rounded-lg px-4 py-3 bg-destructive/10 text-destructive",
                "flex items-center justify-between gap-3 text-sm"
              )}
              role="alert"
            >
              <span>{error}</span>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={dismissError}
                aria-label="Dismiss error"
              >
                <X className="size-3.5" />
              </Button>
            </div>
          )}

          {/* Scroll sentinel */}
          <div ref={sentinelRef} aria-hidden="true" />
        </div>
      </div>

      {/* Input area */}
      <MessageInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
