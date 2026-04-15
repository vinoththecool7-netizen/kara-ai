"use client";

import { useReducer, useRef, useCallback, useEffect } from "react";
import { useSSE } from "@/hooks/useSSE";
import { createChat, continueChat, fetchSession, deleteSession, HttpError } from "@/lib/api";
import type {
  CapitalGainsDetail,
  ChatMessage,
  OptimizationResult,
  ProfileState,
  RegimeComparison,
  TaxBreakdown,
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
  | { type: "SET_TAX_BREAKDOWN"; breakdown: TaxBreakdown }
  | { type: "SET_REGIME_COMPARISON"; comparison: RegimeComparison }
  | { type: "SET_DEDUCTION_GAPS"; optimization: OptimizationResult }
  | { type: "SET_CAPITAL_GAINS"; gains: CapitalGainsDetail[] }
  | { type: "REMOVE_MESSAGE"; id: string }
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
// Helpers
// ---------------------------------------------------------------------------

function lastAssistantIndex(messages: ChatMessage[]): number {
  return messages.reduceRight(
    (found, msg, idx) => (found === -1 && msg.role === "assistant" ? idx : found),
    -1,
  );
}

function markLastAssistantDone(messages: ChatMessage[]): ChatMessage[] {
  const idx = lastAssistantIndex(messages);
  if (idx === -1) return messages;
  return messages.map((msg, i) =>
    i === idx ? { ...msg, isStreaming: false } : msg,
  );
}

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
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = {
        ...messages[idx],
        content: messages[idx].content + action.text,
        isStreaming: true,
      };
      return { ...state, messages };
    }

    case "ADD_TOOL_EVENT": {
      const messages = [...state.messages];
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = {
        ...messages[idx],
        toolEvents: [...(messages[idx].toolEvents ?? []), action.event],
      };
      return { ...state, messages };
    }

    case "SET_SESSION_ID":
      return { ...state, sessionId: action.sessionId };

    case "SET_STREAMING":
      return { ...state, isStreaming: action.streaming };

    case "SET_ERROR": {
      // On failure: drop any trailing empty assistant bubble (so we don't
      // leave an orphaned "typing…" shell), then tag the last user message
      // as failed so the UI can render an inline Retry affordance.
      let messages = state.messages;
      const assistantIdx = lastAssistantIndex(messages);
      if (
        action.error &&
        assistantIdx !== -1 &&
        messages[assistantIdx].content === ""
      ) {
        messages = messages.filter((_, i) => i !== assistantIdx);
      } else {
        messages = markLastAssistantDone(messages);
      }
      if (action.error) {
        // Mark the last user message (if any) as failed
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === "user") {
            messages = messages.map((msg, idx) =>
              idx === i ? { ...msg, status: "failed" as const } : msg,
            );
            break;
          }
        }
      }
      return {
        ...state,
        error: action.error,
        isStreaming: false,
        isLoading: false,
        messages,
      };
    }

    case "SET_DONE": {
      const messages = markLastAssistantDone(state.messages);
      const idx = lastAssistantIndex(messages);
      const emptyResponse = idx !== -1 && messages[idx].content.trim() === "";

      if (emptyResponse) {
        return {
          ...state,
          sessionId: action.sessionId,
          profileState: action.profileState,
          isStreaming: false,
          messages: messages.filter((_, i) => i !== idx),
          error: "Kara couldn't generate a response. Please try rephrasing.",
        };
      }

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

    case "SET_TAX_BREAKDOWN": {
      const messages = [...state.messages];
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = { ...messages[idx], taxBreakdown: action.breakdown };
      return { ...state, messages };
    }

    case "SET_REGIME_COMPARISON": {
      const messages = [...state.messages];
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = { ...messages[idx], regimeComparison: action.comparison };
      return { ...state, messages };
    }

    case "SET_DEDUCTION_GAPS": {
      const messages = [...state.messages];
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = { ...messages[idx], deductionGaps: action.optimization };
      return { ...state, messages };
    }

    case "SET_CAPITAL_GAINS": {
      const messages = [...state.messages];
      const idx = lastAssistantIndex(messages);
      if (idx === -1) return state;
      messages[idx] = { ...messages[idx], capitalGains: action.gains };
      return { ...state, messages };
    }

    case "SET_LOADING":
      return { ...state, isLoading: action.loading };

    case "REMOVE_MESSAGE":
      return {
        ...state,
        messages: state.messages.filter((m) => m.id !== action.id),
      };

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
  retryMessage: (id: string) => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChat(): UseChatReturn {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const { processStream, abort } = useSSE();

  // Use a ref to always have the latest sessionId inside async callbacks,
  // without needing to include it in useCallback dependency arrays.
  const sessionIdRef = useRef<string | null>(null);
  sessionIdRef.current = state.sessionId;

  // Same trick for messages — needed so retryMessage can look up content
  // by id without re-creating its useCallback every render.
  const messagesRef = useRef<ChatMessage[]>(state.messages);
  messagesRef.current = state.messages;

  // -------------------------------------------------------------------------
  // sendMessage
  // -------------------------------------------------------------------------

  const sendMessage = useCallback(async (text: string): Promise<void> => {
    // Cancel any in-flight stream before starting a new one
    abort();

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
        onTaxBreakdown: (breakdown) => {
          dispatch({ type: "SET_TAX_BREAKDOWN", breakdown });
        },
        onRegimeComparison: (comparison) => {
          dispatch({ type: "SET_REGIME_COMPARISON", comparison });
        },
        onDeductionGaps: (optimization) => {
          dispatch({ type: "SET_DEDUCTION_GAPS", optimization });
        },
        onCapitalGains: (gains) => {
          dispatch({ type: "SET_CAPITAL_GAINS", gains });
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
        error: "Unable to connect. Check your connection and try again.",
      });
    }
  }, [processStream, abort]);

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
      // If the session no longer exists on the server, clear the stale localStorage key
      // silently rather than showing an error to the user
      if (err instanceof HttpError && err.status === 404) {
        localStorage.removeItem("kara_session_id");
        return;
      }
      const message =
        err instanceof Error ? err.message : "Failed to load session.";
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
  // retryMessage — re-send a previously failed user message.
  // -------------------------------------------------------------------------

  const retryMessage = useCallback(
    async (id: string): Promise<void> => {
      const target = messagesRef.current.find((m) => m.id === id);
      if (!target || target.role !== "user") return;
      // Drop the failed message so sendMessage can add a fresh one
      dispatch({ type: "REMOVE_MESSAGE", id });
      await sendMessage(target.content);
    },
    [sendMessage],
  );

  // -------------------------------------------------------------------------
  // Mount effect: restore session from localStorage
  // -------------------------------------------------------------------------

  // Abort in-flight stream on unmount
  useEffect(() => {
    return () => { abort(); };
  }, [abort]);

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
    retryMessage,
  };
}
