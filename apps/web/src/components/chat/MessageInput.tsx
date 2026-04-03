"use client";

import { useRef, useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_ROWS = 5;
const LINE_HEIGHT = 24; // px, matches leading-6 (1.5rem at 16px base)
const PADDING_Y = 16; // 8px top + 8px bottom (py-2)
const MAX_TEXTAREA_HEIGHT = MAX_ROWS * LINE_HEIGHT + PADDING_Y; // 136px

interface MessageInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function MessageInput({
  onSend,
  disabled = false,
  placeholder = "Ask Kara a tax question…",
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function resizeTextarea(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT) + "px";
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value);
    resizeTextarea(e.target);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
    if (e.key === "Escape") {
      setValue("");
      const el = textareaRef.current;
      if (el) el.style.height = "auto";
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.focus();
    }
  }

  const sendDisabled = disabled || value.trim() === "";

  return (
    <div
      className="border-t border-border bg-background px-4 py-3 sticky bottom-0"
      style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
    >
      {/* Visually hidden label for screen readers */}
      <label htmlFor="kara-message-input" className="sr-only">
        Type your message to Kara
      </label>
      <div className="flex items-end gap-2 max-w-3xl mx-auto w-full">
        <textarea
          id="kara-message-input"
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className={cn(
            "flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2",
            "text-foreground placeholder:text-muted-foreground text-sm leading-6",
            "outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:border-ring",
            "disabled:opacity-50 disabled:cursor-not-allowed overflow-y-auto"
          )}
        />
        <Button
          variant="default"
          size="icon"
          onClick={submit}
          disabled={sendDisabled}
          aria-label="Send message"
          className="min-w-[44px] min-h-[44px] shrink-0 active:scale-95"
        >
          <ArrowUp className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
