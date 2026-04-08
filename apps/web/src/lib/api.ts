/**
 * API client for the Kara chat backend.
 *
 * All requests go through the Next.js proxy defined in next.config.ts:
 *   /api/* → http://localhost:8000/api/*
 *
 * SSE functions return a raw Response so the caller can read
 * response.body as a ReadableStream for streaming events.
 */

import type { SessionResponse, SessionSummary } from "@/types/chat";

const API_PREFIX = "/api/v1/chat";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function buildJsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

async function assertOk(response: Response, context: string): Promise<void> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.clone().json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore parse errors — keep statusText as the message
    }
    throw new HttpError(
      response.status,
      `[${context}] HTTP ${response.status}: ${detail}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

/**
 * Start a new chat session.
 *
 * Returns the raw Response so the caller can parse the SSE stream via
 * response.body (ReadableStream). The backend streams Server-Sent Events.
 */
export async function createChat(message: string): Promise<Response> {
  const response = await fetch(API_PREFIX, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify({ message }),
  });

  await assertOk(response, "createChat");
  return response;
}

/**
 * Send a follow-up message in an existing chat session.
 *
 * Returns the raw Response so the caller can parse the SSE stream via
 * response.body (ReadableStream). The backend streams Server-Sent Events.
 */
export async function continueChat(
  sessionId: string,
  message: string
): Promise<Response> {
  const response = await fetch(`${API_PREFIX}/${sessionId}`, {
    method: "POST",
    headers: buildJsonHeaders(),
    body: JSON.stringify({ message }),
  });

  await assertOk(response, "continueChat");
  return response;
}

/**
 * Fetch full session details including message history and profile state.
 *
 * Returns parsed JSON as a SessionResponse.
 */
export async function fetchSession(
  sessionId: string
): Promise<SessionResponse> {
  const response = await fetch(`${API_PREFIX}/${sessionId}`, {
    method: "GET",
    headers: buildJsonHeaders(),
  });

  await assertOk(response, "fetchSession");
  return response.json() as Promise<SessionResponse>;
}

/**
 * Delete a chat session and all associated data.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_PREFIX}/${sessionId}`, {
    method: "DELETE",
    headers: buildJsonHeaders(),
  });

  await assertOk(response, "deleteSession");
}

/**
 * List all chat sessions, newest first, for the sidebar.
 *
 * Each entry carries a server-derived `title` (first user message
 * truncated to 60 characters, or `"New Chat"` when empty) and a total
 * `message_count`.
 */
export async function listSessions(): Promise<SessionSummary[]> {
  const response = await fetch(`${API_PREFIX}/sessions`, {
    method: "GET",
    headers: buildJsonHeaders(),
  });

  await assertOk(response, "listSessions");
  return response.json() as Promise<SessionSummary[]>;
}
