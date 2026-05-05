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
import { reportNetworkError } from "@/hooks/useOnlineStatus";

const API_PREFIX = "/api/v1/chat";

interface RetryOptions {
  retries?: number;
  backoffMs?: number;
}

async function fetchWithRetry(
  input: RequestInfo | URL,
  init: RequestInit,
  { retries = 0, backoffMs = 400 }: RetryOptions = {},
): Promise<Response> {
  let attempt = 0;
  let lastError: unknown;
  while (attempt <= retries) {
    try {
      const response = await fetch(input, init);
      if (response.status >= 500 && attempt < retries) {
        attempt++;
        await new Promise((r) => setTimeout(r, backoffMs * attempt));
        continue;
      }
      return response;
    } catch (err) {
      lastError = err;
      if (attempt < retries) {
        attempt++;
        await new Promise((r) => setTimeout(r, backoffMs * attempt));
        continue;
      }
      reportNetworkError();
      throw lastError;
    }
  }
  throw lastError ?? new Error("fetchWithRetry: exhausted retries");
}

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
  let response: Response;
  try {
    response = await fetch(API_PREFIX, {
      method: "POST",
      headers: buildJsonHeaders(),
      body: JSON.stringify({ message }),
    });
  } catch (err) {
    reportNetworkError();
    throw err;
  }

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
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}/${sessionId}`, {
      method: "POST",
      headers: buildJsonHeaders(),
      body: JSON.stringify({ message }),
    });
  } catch (err) {
    reportNetworkError();
    throw err;
  }

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
  const response = await fetchWithRetry(
    `${API_PREFIX}/${sessionId}`,
    { method: "GET", headers: buildJsonHeaders() },
    { retries: 2 },
  );

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
  const response = await fetchWithRetry(
    `${API_PREFIX}/sessions`,
    { method: "GET", headers: buildJsonHeaders() },
    { retries: 2 },
  );

  await assertOk(response, "listSessions");
  return response.json() as Promise<SessionSummary[]>;
}

// ---------------------------------------------------------------------------
// Document upload
// ---------------------------------------------------------------------------

export interface DocumentUploadResponse {
  document_id: string;
  document_type: string;
  parsed_summary: {
    document_id: string;
    document_type: string;
    pan: string | null;
    employer_name: string | null;
    period: string | null;
    key_amounts: Record<string, number>;
    fields_filled: number;
  };
  profile_diff: {
    slots_added: Record<string, unknown>;
    slots_overridden: Record<string, unknown[]>;
    warnings: string[];
  };
  warnings: string[];
}

const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Upload a tax document (Form 16, AIS, 26AS) for parsing.
 *
 * Client-side guards: throws HttpError(413) if the file exceeds 10 MB.
 * Uses indeterminate-progress fetch (no XHR) — spinner in the UI is
 * sufficient given typical document sizes.
 */
export async function uploadDocument(
  sessionId: string,
  file: File,
  documentType: "form16" | "ais" | "26as" | "auto" = "auto",
): Promise<DocumentUploadResponse> {
  if (file.size > DOCUMENT_MAX_BYTES) {
    throw new HttpError(413, "File too large. Maximum is 10 MB.");
  }

  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("document_type", documentType);
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch("/api/v1/documents/upload", {
      method: "POST",
      // No Content-Type header — let the browser set multipart/form-data boundary
      body: formData,
    });
  } catch (err) {
    reportNetworkError();
    throw err;
  }

  await assertOk(response, "uploadDocument");
  return response.json() as Promise<DocumentUploadResponse>;
}
