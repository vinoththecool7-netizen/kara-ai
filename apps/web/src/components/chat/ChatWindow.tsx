"use client";

import { useRef, useEffect, useCallback } from "react";
import { X, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
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

export function ChatWindow() {
  const {
    messages,
    isStreaming,
    isLoading,
    error,
    sendMessage,
    dismissError,
  } = useChat();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const lastRetryRef = useRef<string | null>(null);

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

  // Retry: re-send the last user message
  function handleRetry() {
    // Find the last user message
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastRetryRef.current = messages[i].content;
        dismissError();
        sendMessage(messages[i].content);
        return;
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
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
                size="lg"
                className="size-16 bg-kara-primary text-primary-foreground"
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
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {showTypingIndicator && <TypingIndicator />}

          {/* Error banner */}
          {error && (
            <div
              className={cn(
                "rounded-lg px-4 py-3 bg-destructive/10 text-destructive",
                "flex items-center justify-between gap-3 text-sm"
              )}
              role="alert"
            >
              <span>{error}</span>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={handleRetry}
                  aria-label="Retry"
                >
                  <RotateCcw className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={dismissError}
                  aria-label="Dismiss error"
                >
                  <X className="size-3.5" />
                </Button>
              </div>
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
