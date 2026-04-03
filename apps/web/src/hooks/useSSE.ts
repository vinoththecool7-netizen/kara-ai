"use client";

import { useRef, useState } from "react";
import type { SSEEvent, ProfileState } from "@/types/chat";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface UseSSECallbacks {
  onSessionCreated?: (sessionId: string) => void;
  onToolResult?: (toolName: string, result: unknown, isError: boolean) => void;
  onContent?: (text: string) => void;
  onContentDelta?: (text: string) => void; // forward-compatible with future token streaming
  onAdvisory?: (hint: string) => void;
  onDone?: (sessionId: string, profileState: ProfileState) => void;
  onError?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Low-level hook that reads an SSE stream from a fetch Response and dispatches
 * typed events to caller-supplied callbacks.
 *
 * We use fetch + ReadableStream instead of EventSource because the backend
 * uses POST for its SSE endpoints, and the browser EventSource API only
 * supports GET.
 *
 * SSE wire format from the backend:
 *   data: {"type":"...","key":"value"}\n\n
 */
export function useSSE(): {
  processStream: (response: Response, callbacks: UseSSECallbacks) => Promise<void>;
  abort: () => void;
  isStreaming: boolean;
} {
  const abortControllerRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // -------------------------------------------------------------------------
  // dispatch — route a parsed SSEEvent to the appropriate callback
  // -------------------------------------------------------------------------

  function dispatch(event: SSEEvent, callbacks: UseSSECallbacks): void {
    switch (event.type) {
      case "session_created":
        callbacks.onSessionCreated?.(event.session_id);
        break;
      case "tool_result":
        callbacks.onToolResult?.(event.tool_name, event.result, event.is_error);
        break;
      case "content":
        callbacks.onContent?.(event.text);
        break;
      case "content_delta":
        callbacks.onContentDelta?.(event.text);
        break;
      case "advisory":
        callbacks.onAdvisory?.(event.hint);
        break;
      case "done":
        callbacks.onDone?.(event.session_id, event.profile_state);
        break;
      case "error":
        callbacks.onError?.(event.message);
        break;
    }
  }

  // -------------------------------------------------------------------------
  // processStream — consume the ReadableStream from a fetch Response
  // -------------------------------------------------------------------------

  async function processStream(
    response: Response,
    callbacks: UseSSECallbacks
  ): Promise<void> {
    // Create a fresh AbortController for this stream.
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (!response.body) {
      callbacks.onError?.("Response has no body");
      return;
    }

    setIsStreaming(true);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    // Accumulate bytes that haven't yet formed a complete SSE event.
    let buffer = "";

    try {
      while (true) {
        // Honour abort requests between chunk reads.
        if (controller.signal.aborted) break;

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by a blank line (\n\n).
        // Split on every \n\n; the last element is whatever incomplete
        // fragment remains (may be an empty string).
        const parts = buffer.split("\n\n");
        // Keep the trailing incomplete fragment in the buffer.
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          // Each part may contain multiple lines (e.g. "event: ...\ndata: ...").
          // We only care about lines that start with "data: ".
          for (const line of part.split("\n")) {
            if (!line.startsWith("data: ")) continue;

            const payload = line.slice("data: ".length);
            try {
              const event = JSON.parse(payload) as SSEEvent;
              dispatch(event, callbacks);
            } catch {
              // Skip malformed JSON — don't crash the stream.
            }
          }
        }
      }
    } catch (err) {
      // AbortError is expected when the user calls abort(); swallow it.
      if (err instanceof Error && err.name === "AbortError") {
        // intentional abort — no callback needed
      } else {
        // Surface unexpected read errors to the caller.
        const message =
          err instanceof Error ? err.message : "Unknown stream error";
        callbacks.onError?.(message);
      }
    } finally {
      // Release the lock on the stream and reset state.
      reader.releaseLock();
      setIsStreaming(false);
    }
  }

  // -------------------------------------------------------------------------
  // abort — cancel an in-progress stream
  // -------------------------------------------------------------------------

  function abort(): void {
    abortControllerRef.current?.abort();
  }

  return { processStream, abort, isStreaming };
}
