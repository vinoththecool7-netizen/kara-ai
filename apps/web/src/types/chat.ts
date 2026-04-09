/**
 * TypeScript interfaces matching the FastAPI backend models.
 * Backend source: apps/api/src/kara_api/routers/chat.py lines 43-73
 */

// ---------------------------------------------------------------------------
// Backend models (mirrors Pydantic models in chat.py)
// ---------------------------------------------------------------------------

export interface ChatRequest {
  message: string;
}

export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
}

export interface MessageResponse {
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls: ToolCallRecord[] | null;
  created_at: string;
}

export interface ProfileState {
  slots: Record<string, unknown>;
  ready_intents: string[];
}

export interface SessionResponse {
  session_id: string;
  created_at: string;
  profile_state: ProfileState;
  messages: MessageResponse[];
}

/**
 * Lightweight projection of a session for the sidebar listing.
 *
 * Mirrors `SessionSummary` in apps/api/src/kara_api/routers/chat.py.
 * `title` is derived server-side from the first user message (truncated to
 * 60 characters with an ellipsis, or `"New Chat"` when empty).
 */
export interface SessionSummary {
  id: string;
  created_at: string;
  updated_at: string;
  title: string;
  message_count: number;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  tool_calls_made: {
    tool_name: string;
    arguments: Record<string, unknown>;
    result: string;
    is_error: boolean;
  }[];
  profile_state: ProfileState;
}

// ---------------------------------------------------------------------------
// SSE event discriminated union
// Supports both current (full response) and future (token-by-token) streaming.
// ---------------------------------------------------------------------------

export type SSEEvent =
  | { type: "session_created"; session_id: string }
  | { type: "tool_result"; tool_name: string; result: unknown; is_error: boolean }
  | { type: "content"; text: string }       // current: full response at once
  | { type: "content_delta"; text: string } // future: incremental token stream
  | { type: "advisory"; hint: string }
  | { type: "done"; session_id: string; profile_state: ProfileState }
  | { type: "error"; message: string };

// ---------------------------------------------------------------------------
// Client-side models (adds UI state not present in API responses)
// ---------------------------------------------------------------------------

export interface ToolEvent {
  toolName: string;
  result?: unknown;
  isError: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  toolEvents?: ToolEvent[];
  /**
   * Delivery status. Only populated for user messages that failed to send;
   * absent (undefined) means "sent successfully".
   */
  status?: "failed";
}
