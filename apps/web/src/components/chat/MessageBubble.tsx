"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, AlertCircle, RotateCcw } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";
import { TaxBreakdownCard } from "@/components/cards/TaxBreakdownCard";
import { RegimeComparisonCard } from "@/components/cards/RegimeComparisonCard";
import { DeductionGapCard } from "@/components/cards/DeductionGapCard";
import { CapitalGainsCard } from "@/components/cards/CapitalGainsCard";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${diffDay}d ago`;
}

function humanizeToolName(name: string): string {
  // snake_case → Title Case words
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

// ---------------------------------------------------------------------------
// Markdown component overrides for react-markdown v10+
// ---------------------------------------------------------------------------

const markdownComponents: React.ComponentProps<
  typeof ReactMarkdown
>["components"] = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => (
    <ul className="list-disc pl-4 mb-2">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-4 mb-2">{children}</ol>
  ),
  li: ({ children }) => <li className="mb-0.5">{children}</li>,
  // In react-markdown v10, code blocks are wrapped by <pre> automatically.
  // The `code` element receives className="language-*" for fenced blocks
  // and no className for inline code.
  code: ({ className, children, ...props }) => {
    const isCodeBlock = Boolean(className?.startsWith("language-"));
    return (
      <code
        className={cn(
          "font-mono text-sm",
          isCodeBlock
            ? "block bg-foreground/10 p-3 rounded-lg overflow-x-auto"
            : "bg-foreground/10 px-1 py-0.5 rounded"
        )}
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="mb-2 last:mb-0">{children}</pre>,
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-primary underline underline-offset-2"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <table className="border-collapse border border-border text-sm my-2 w-full">
      {children}
    </table>
  ),
  th: ({ children }) => (
    <th className="border border-border px-2 py-1 bg-muted font-semibold text-left">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-2 py-1">{children}</td>
  ),
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MessageBubbleProps {
  message: ChatMessage;
  /** Called when the user clicks "Retry" on a failed user message. */
  onRetry?: (id: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isFailed = isUser && message.status === "failed";
  const isoTimestamp = message.timestamp.toISOString();
  const relativeTime = formatRelativeTime(message.timestamp);
  const fullTimestamp = message.timestamp.toLocaleString();
  const [copied, setCopied] = useState(false);

  // Reset the "Copied!" state after 2 seconds
  useEffect(() => {
    if (!copied) return;
    const timeout = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timeout);
  }, [copied]);

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
    } catch {
      // Clipboard API may be unavailable on insecure origins; fail silently.
    }
  }

  return (
    <div
      className={cn(
        "group flex flex-col gap-1 animate-in fade-in duration-200 motion-reduce:animate-none",
        isUser ? "items-end" : "items-start"
      )}
    >
      {/* Tool event badges — shown above the bubble for assistant messages */}
      {!isUser &&
        message.toolEvents &&
        message.toolEvents.length > 0 && (
          <div className="flex flex-wrap gap-1 pl-10">
            {message.toolEvents.map((event, idx) => (
              <Badge key={idx} variant="secondary" className="text-xs">
                {humanizeToolName(event.toolName)}
              </Badge>
            ))}
          </div>
        )}

      {/* Message row */}
      <div
        className={cn(
          "flex gap-2 items-end",
          isUser ? "flex-row-reverse" : "flex-row"
        )}
      >
        {/* Avatar — only for assistant */}
        {!isUser && (
          <Avatar size="sm" className="shrink-0 mb-0.5">
            <AvatarFallback className="bg-kara-primary text-white">
              K
            </AvatarFallback>
          </Avatar>
        )}

        {/* Bubble */}
        <div
          className={cn(
            "max-w-[85%] sm:max-w-[75%] px-4 py-2.5",
            isUser
              ? isFailed
                ? "bg-destructive/10 text-foreground border border-destructive/40 rounded-2xl rounded-br-sm"
                : "bg-primary text-primary-foreground rounded-2xl rounded-br-sm"
              : "bg-muted text-foreground rounded-2xl rounded-bl-sm"
          )}
          aria-invalid={isFailed || undefined}
        >
          {isUser ? (
            // Plain text for user messages
            <span className="whitespace-pre-wrap break-words">
              {message.content}
            </span>
          ) : (
            // Markdown for assistant messages
            <div className="prose-sm break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {message.content}
              </ReactMarkdown>
              {/* Streaming cursor */}
              {message.isStreaming && (
                <span
                  aria-hidden="true"
                  className="inline-block w-0.5 h-4 bg-foreground animate-pulse ml-0.5 align-text-bottom"
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tax breakdown card — rendered outside the bubble for full width */}
      {!isUser && message.taxBreakdown && !message.isStreaming && (
        <div className="pl-10 w-full">
          <TaxBreakdownCard breakdown={message.taxBreakdown} />
        </div>
      )}

      {/* Regime comparison card — rendered outside the bubble for full width */}
      {!isUser && message.regimeComparison && !message.isStreaming && (
        <div className="pl-10 w-full">
          <RegimeComparisonCard comparison={message.regimeComparison} />
        </div>
      )}

      {/* Deduction gap card — rendered outside the bubble for full width */}
      {!isUser && message.deductionGaps && !message.isStreaming && (
        <div className="pl-10 w-full">
          <DeductionGapCard optimization={message.deductionGaps} />
        </div>
      )}

      {/* Capital gains card — rendered outside the bubble for full width */}
      {!isUser && message.capitalGains && message.capitalGains.length > 0 && !message.isStreaming && (
        <div className="pl-10 w-full">
          <CapitalGainsCard gains={message.capitalGains} />
        </div>
      )}

      {/* Timestamp + per-message actions */}
      <div
        className={cn(
          "flex items-center gap-2 text-xs mt-1",
          isFailed ? "text-destructive" : "text-muted-foreground",
          isUser ? "pr-1" : "pl-10"
        )}
      >
        {isFailed && (
          <span className="inline-flex items-center gap-1" aria-hidden="true">
            <AlertCircle className="size-3.5" />
            Failed to send
          </span>
        )}
        {isFailed && onRetry && (
          <button
            type="button"
            onClick={() => onRetry(message.id)}
            aria-label="Retry sending this message"
            className={cn(
              "inline-flex items-center gap-1 px-2 h-8 rounded",
              "text-destructive hover:bg-destructive/10",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/40",
            )}
          >
            <RotateCcw className="size-3.5" />
            Retry
          </button>
        )}
        {!isFailed && (
          <time dateTime={isoTimestamp} aria-label={fullTimestamp}>
            {relativeTime}
          </time>
        )}

        {/* Copy button — assistant bubbles only.
            Hidden until hover/focus on devices with hover; always shown on
            touch devices (no hover capability). */}
        {!isUser && message.content && !message.isStreaming && (
          <button
            type="button"
            onClick={handleCopy}
            aria-label={copied ? "Copied" : "Copy message"}
            className={cn(
              "size-8 inline-flex items-center justify-center rounded",
              "text-muted-foreground hover:text-foreground hover:bg-muted",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
              "opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
              "transition-opacity duration-150 motion-reduce:transition-none",
              "[@media(hover:none)]:opacity-100",
            )}
          >
            {copied ? (
              <Check className="size-3.5 text-green-600 dark:text-green-400" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        )}

        {/* Screen reader announcement for copy success */}
        {copied && (
          <span role="status" aria-live="polite" className="sr-only">
            Message copied
          </span>
        )}
      </div>
    </div>
  );
}
