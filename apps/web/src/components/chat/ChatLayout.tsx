"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useChat } from "@/hooks/useChat";
import { useSessions } from "@/hooks/useSessions";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { toast } from "@/hooks/useToast";
import { getSetupStatus } from "@/lib/api";
import { ChatWindow } from "./ChatWindow";
import { SessionSidebar } from "./SessionSidebar";

/**
 * Top-level chat orchestrator. Owns both `useChat` and `useSessions`
 * so the sidebar and chat window share session state.
 *
 * Layout:
 *   - Desktop (>=md): two-column grid (sidebar | chat window)
 *   - Mobile (<md):   single column with sidebar as a slide-in drawer
 */
export function ChatLayout() {
  const chat = useChat();
  const sessionsState = useSessions();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const router = useRouter();

  // First-run guard: an unconfigured backend can't chat — send the user to
  // the setup wizard instead of letting the first message fail.
  useEffect(() => {
    getSetupStatus()
      .then((s) => {
        if (!s.configured) router.replace("/setup");
      })
      .catch(() => {
        // API unreachable → the chat UI's own error handling covers it.
      });
  }, [router]);

  // Whenever the active sessionId changes (e.g. a new session was just
  // created via the first message), refresh the sidebar list so the new
  // entry appears at the top.
  useEffect(() => {
    if (chat.sessionId) {
      void sessionsState.refetch();
    }
    // sessionsState.refetch is intentionally omitted to avoid an infinite loop;
    // the function identity changes every render but its behavior is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.sessionId]);

  const handleSelect = async (id: string) => {
    if (id === chat.sessionId) return;
    await chat.loadSession(id);
  };

  const handleNewChat = useCallback(() => {
    chat.clearChat();
    void sessionsState.refetch();
  }, [chat, sessionsState]);

  // Global keyboard shortcuts: Ctrl/Cmd+K focuses the input,
  // Ctrl/Cmd+Shift+N starts a new chat.
  useKeyboardShortcuts({
    onFocusInput: useCallback(() => {
      const el = document.getElementById(
        "kara-message-input",
      ) as HTMLTextAreaElement | null;
      el?.focus();
    }, []),
    onNewChat: handleNewChat,
  });

  const handleDelete = async (id: string) => {
    try {
      await sessionsState.removeSession(id);
      toast.success("Chat deleted");
      // If the deleted session is the one currently open, reset the chat.
      if (id === chat.sessionId) {
        chat.clearChat();
      }
    } catch {
      toast.error("Couldn't delete chat");
      // The hook already rolled the optimistic removal back; nothing to do.
    }
  };

  return (
    <div className="h-full md:grid md:grid-cols-[280px_1fr]">
      <SessionSidebar
        sessions={sessionsState.sessions}
        currentSessionId={chat.sessionId}
        isLoading={sessionsState.isLoading}
        error={sessionsState.error}
        onSelect={handleSelect}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
        onRetry={sessionsState.refetch}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
      <div className="h-full min-w-0">
        <ChatWindow
          chat={chat}
          onOpenSidebar={() => setDrawerOpen(true)}
          sidebarOpen={drawerOpen}
        />
      </div>
    </div>
  );
}
