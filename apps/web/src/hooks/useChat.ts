"use client";

import { useReducer, useRef, useCallback, useEffect } from "react";
import { useSSE } from "@/hooks/useSSE";
import { createChat, continueChat, fetchSession, deleteSession } from "@/lib/api";
import type {
  ChatMessage,
  ProfileState,
  ToolEvent,
} from "@/types/chat";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  isStreaming: boolean;
  error: string | null;
  profileState: ProfileState | null;
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

type ChatAction =
  | { type: "ADD_USER_MESSAGE"; message: ChatMessage }
  | { type: "ADD_ASSISTANT_MESSAGE"; message: ChatMessage }
  | { type: "APPEND_CONTENT"; text: string }
  | { type: "ADD_TOOL_EVENT"; event: ToolEvent }
  | { type: "SET_SESSION_ID"; sessionId: string }
  | { type: "SET_STREAMING"; streaming: boolean }
  | { type: "SET_ERROR"; error: string | null }
  | { type: "SET_DONE"; sessionId: string; profileState: ProfileState }
  | { type: "LOAD_HISTORY"; sessionId: string; messages: ChatMessage[]; profileState: ProfileState }
  | { type: "SET_LOADING"; loading: boolean }
  | { type: "CLEAR" };

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState: ChatState = {
  messages: [],
  sessionId: null,
  isStreaming: false,
  error: null,
  profileState: null,
  isLoading: false,
};

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "ADD_USER_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };

    case "ADD_ASSISTANT_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };

    case "APPEND_CONTENT": {
      const messages = [...state.messages];
      // Find last assistant message
      const lastIndex = messages.reduceRight(
        (found, msg, i) => (found === -1 && msg.role === "assistant" ? i : found),
        -1
      );
      if (lastIndex === -1) return state;
      messages[lastIndex] = {
        ...messages[lastIndex],
        content: messages[lastIndex].content + action.text,
        isStreaming: true,
      };
      return { ...state, messages };
    }

    case "ADD_TOOL_EVENT": {
      const messages = [...state.messages];
      const lastIndex = messages.reduceRight(
        (found, msg, i) => (found === -1 && msg.role === "assistant" ? i : found),
        -1
      );
      if (lastIndex === -1) return state;
      const existing = messages[lastIndex];
      messages[lastIndex] = {
        ...existing,
        toolEvents: [...(existing.toolEvents ?? []), action.event],
      };
      return { ...state, messages };
    }

    case "SET_SESSION_ID":
      return { ...state, sessionId: action.sessionId };

    case "SET_STREAMING": {
      if (action.streaming) {
        return { ...state, isStreaming: true };
      }
      // When stopping streaming, also mark last assistant message's isStreaming false
      const messages = state.messages.map((msg, i, arr) => {
        const isLast = i === arr.length - 1 || arr.slice(i + 1).every((m) => m.role !== "assistant");
        if (msg.role === "assistant" && i === arr.reduceRight(
          (found, m, idx) => (found === -1 && m.role === "assistant" ? idx : found),
          -1
        )) {
          return { ...msg, isStreaming: false };
        }
        return msg;
      });
      return { ...state, isStreaming: false, messages };
    }

    case "SET_ERROR": {
      const messages = state.messages.map((msg, i, arr) => {
        const lastAssistantIdx = arr.reduceRight(
          (found, m, idx) => (found === -1 && m.role === "assistant" ? idx : found),
          -1
        );
        if (msg.role === "assistant" && i === lastAssistantIdx) {
          return { ...msg, isStreaming: false };
        }
        return msg;
      });
      return { ...state, error: action.error, isStreaming: false, messages };
    }

    case "SET_DONE": {
      const messages = state.messages.map((msg, i, arr) => {
        const lastAssistantIdx = arr.reduceRight(
          (found, m, idx) => (found === -1 && m.role === "assistant" ? idx : found),
          -1
        );
        if (msg.role === "assistant" && i === lastAssistantIdx) {
          return { ...msg, isStreaming: false };
        }
        return msg;
      });
      return {
        ...state,
        sessionId: action.sessionId,
        profileState: action.profileState,
        isStreaming: false,
        messages,
      };
    }

    case "LOAD_HISTORY":
      return {
        ...state,
        sessionId: action.sessionId,
        messages: action.messages,
        profileState: action.profileState,
        isLoading: false,
      };

    case "SET_LOADING":
      return { ...state, isLoading: action.loading };

    case "CLEAR":
      return { ...initialState };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Public return type
// ---------------------------------------------------------------------------

export interface UseChatReturn {
  messages: ChatMessage[];
  sessionId: string | null;
  isStreaming: boolean;
  error: string | null;
  profileState: ProfileState | null;
  isLoading: boolean;
  sendMessage: (text: string) => Promise<void>;
  clearChat: () => void;
  loadSession: (sessionId: string) => Promise<void>;
  dismissError: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChat(): UseChatReturn {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const { processStream } = useSSE();

  // Use a ref to always have the latest sessionId inside async callbacks,
  // without needing to include it in useCallback dependency arrays.
  const sessionIdRef = useRef<string | null>(null);
  sessionIdRef.current = state.sessionId;

  // -------------------------------------------------------------------------
  // sendMessage
  // -------------------------------------------------------------------------

  const sendMessage = useCallback(async (text: string): Promise<void> => {
    // 1. Clear any existing error
    dispatch({ type: "SET_ERROR", error: null });

    // 2. Create and dispatch user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    dispatch({ type: "ADD_USER_MESSAGE", message: userMessage });

    // 3. Set streaming state
    dispatch({ type: "SET_STREAMING", streaming: true });

    // 4. Create and dispatch empty assistant message
    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isStreaming: true,
      toolEvents: [],
    };
    dispatch({ type: "ADD_ASSISTANT_MESSAGE", message: assistantMessage });

    try {
      // 5. Call API — use the ref to get the current sessionId at call time
      const currentSessionId = sessionIdRef.current;
      const response = currentSessionId
        ? await continueChat(currentSessionId, text)
        : await createChat(text);

      // 6. Process the SSE stream
      await processStream(response, {
        onSessionCreated: (sessionId) => {
          dispatch({ type: "SET_SESSION_ID", sessionId });
          // Keep ref in sync immediately (reducer updates async via re-render)
          sessionIdRef.current = sessionId;
          // Persist so the session survives a page refresh
          localStorage.setItem("kara_session_id", sessionId);
        },
        onToolResult: (toolName, result, isError) => {
          dispatch({
            type: "ADD_TOOL_EVENT",
            event: { toolName, result, isError },
          });
        },
        onContent: (text) => {
          dispatch({ type: "APPEND_CONTENT", text });
        },
        onContentDelta: (text) => {
          dispatch({ type: "APPEND_CONTENT", text });
        },
        onAdvisory: (hint) => {
          console.log("[Advisory]", hint);
        },
        onDone: (sessionId, profileState) => {
          dispatch({ type: "SET_DONE", sessionId, profileState });
          sessionIdRef.current = sessionId;
        },
        onError: (message) => {
          dispatch({ type: "SET_ERROR", error: message });
        },
      });
    } catch {
      dispatch({
        type: "SET_ERROR",
        error: "Unable to connect. Please check your connection and try again.",
      });
    }
  }, [processStream]);

  // -------------------------------------------------------------------------
  // clearChat
  // -------------------------------------------------------------------------

  const clearChat = useCallback((): void => {
    const prevSessionId = sessionIdRef.current;
    dispatch({ type: "CLEAR" });
    sessionIdRef.current = null;
    localStorage.removeItem("kara_session_id");
    // Best-effort server-side deletion — ignore errors
    if (prevSessionId) {
      deleteSession(prevSessionId).catch(() => undefined);
    }
  }, []);

  // -------------------------------------------------------------------------
  // loadSession
  // -------------------------------------------------------------------------

  const loadSession = useCallback(async (sessionId: string): Promise<void> => {
    dispatch({ type: "SET_LOADING", loading: true });
    try {
      const session = await fetchSession(sessionId);
      const messages: ChatMessage[] = session.messages
        .filter((m) => m.role !== "tool")
        .map((m) => ({
          id: crypto.randomUUID(),
          role: m.role as "user" | "assistant",
          content: m.content ?? "",
          timestamp: new Date(m.created_at),
        }));
      dispatch({
        type: "LOAD_HISTORY",
        sessionId: session.session_id,
        messages,
        profileState: session.profile_state,
      });
      sessionIdRef.current = session.session_id;
    } catch (err) {
      dispatch({ type: "SET_LOADING", loading: false });
      const message =
        err instanceof Error ? err.message : "Failed to load session.";
      // If the session no longer exists on the server, clear the stale localStorage key
      // silently rather than showing an error to the user
      if (message.includes("404")) {
        localStorage.removeItem("kara_session_id");
        return;
      }
      dispatch({ type: "SET_ERROR", error: message });
    }
  }, []);

  // -------------------------------------------------------------------------
  // dismissError
  // -------------------------------------------------------------------------

  const dismissError = useCallback((): void => {
    dispatch({ type: "SET_ERROR", error: null });
  }, []);

  // -------------------------------------------------------------------------
  // Mount effect: restore session from localStorage
  // -------------------------------------------------------------------------

  useEffect(() => {
    const storedId = localStorage.getItem("kara_session_id");
    if (!storedId) return;
    // loadSession handles 404 by clearing localStorage silently
    loadSession(storedId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once on mount

  return {
    messages: state.messages,
    sessionId: state.sessionId,
    isStreaming: state.isStreaming,
    error: state.error,
    profileState: state.profileState,
    isLoading: state.isLoading,
    sendMessage,
    clearChat,
    loadSession,
    dismissError,
  };
}
