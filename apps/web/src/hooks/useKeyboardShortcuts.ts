"use client";

import { useEffect } from "react";

interface KeyboardShortcutHandlers {
  /** Called when the user hits Ctrl/Cmd+K — focuses the message input. */
  onFocusInput: () => void;
  /** Called when the user hits Ctrl/Cmd+Shift+N — starts a fresh chat. */
  onNewChat: () => void;
}

/**
 * Registers global keyboard shortcuts for the chat surface.
 *
 *   Ctrl/Cmd+K         → focus the message input
 *   Ctrl/Cmd+Shift+N   → start a new chat
 *
 * Both use `preventDefault()` to override any conflicting browser defaults
 * (Chrome/Firefox Ctrl+K opens the address/search bar, for example).
 */
export function useKeyboardShortcuts({
  onFocusInput,
  onNewChat,
}: KeyboardShortcutHandlers): void {
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      const mod = event.ctrlKey || event.metaKey;
      if (!mod) return;

      const key = event.key.toLowerCase();

      // Ctrl/Cmd+K — focus the message input
      if (key === "k" && !event.shiftKey) {
        event.preventDefault();
        onFocusInput();
        return;
      }

      // Ctrl/Cmd+Shift+N — start a new chat
      if (key === "n" && event.shiftKey) {
        event.preventDefault();
        onNewChat();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onFocusInput, onNewChat]);
}
