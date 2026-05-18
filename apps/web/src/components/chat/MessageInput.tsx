"use client";

import { useRef, useEffect, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useFileDrop } from "@/hooks/useFileDrop";

const MAX_ROWS = 5;
const LINE_HEIGHT = 24; // px, matches leading-6 (1.5rem at 16px base)
const PADDING_Y = 16; // 8px top + 8px bottom (py-2)
const MAX_TEXTAREA_HEIGHT = MAX_ROWS * LINE_HEIGHT + PADDING_Y; // 136px

const ACCEPTED_EXTENSIONS = [".pdf", ".json"];
const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB

interface MessageInputProps {
  onSend: (text: string, files?: File[]) => void;
  onFilesSelected?: (files: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function MessageInput({
  onSend,
  onFilesSelected,
  disabled = false,
  placeholder = "Ask Kara a tax question…",
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);

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

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setStagedFiles((prev) => [...prev, ...files]);
    onFilesSelected?.(files);
    // Reset so the same file can be re-selected if removed
    e.target.value = "";
  }

  function handleFiles(files: File[]) {
    setStagedFiles((prev) => [...prev, ...files]);
    onFilesSelected?.(files);
  }

  function handleReject(reason: string) {
    // Import toast lazily to avoid circular dep — use dynamic import pattern
    import("@/hooks/useToast").then(({ toast }) => {
      toast.error(reason);
    });
  }

  const { isDragging, dragHandlers } = useFileDrop({
    accept: ACCEPTED_EXTENSIONS,
    maxBytes: MAX_FILE_BYTES,
    onFiles: handleFiles,
    onReject: handleReject,
  });

  function submit() {
    const trimmed = value.trim();
    const hasFiles = stagedFiles.length > 0;
    if ((!trimmed && !hasFiles) || disabled) return;
    onSend(trimmed, stagedFiles.length > 0 ? stagedFiles : undefined);
    setValue("");
    setStagedFiles([]);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.focus();
    }
  }

  const sendDisabled = disabled || (value.trim() === "" && stagedFiles.length === 0);

  return (
    <div
      className="border-t border-border bg-background px-4 py-3 sticky bottom-0"
      style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
      {...dragHandlers}
    >
      {/* Drag-over overlay */}
      {isDragging && (
        <div
          aria-hidden="true"
          className={cn(
            "absolute inset-0 z-10 rounded-xl",
            "flex items-center justify-center",
            "border-2 border-dashed border-blue-500",
            "bg-blue-50/80 backdrop-blur-sm",
            "motion-safe:transition-opacity motion-safe:duration-150 motion-safe:ease-out",
          )}
        >
          <span className="text-sm font-medium text-blue-700 select-none pointer-events-none">
            Drop your Form 16, AIS, or 26AS
          </span>
        </div>
      )}

      {/* Staged file chips */}
      {stagedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 max-w-3xl mx-auto w-full mb-2">
          {stagedFiles.map((file, idx) => (
            <div
              key={idx}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium"
            >
              <Paperclip className="size-3" aria-hidden="true" />
              <span className="max-w-[140px] truncate">{file.name}</span>
              <button
                type="button"
                aria-label={`Remove ${file.name}`}
                className="ml-0.5 hover:text-blue-900 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-full"
                onClick={() =>
                  setStagedFiles((prev) => prev.filter((_, i) => i !== idx))
                }
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Visually hidden label for screen readers */}
      <label htmlFor="kara-message-input" className="sr-only">
        Type your message to Kara
      </label>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="sr-only"
        onChange={handleFileInputChange}
        aria-hidden="true"
        tabIndex={-1}
      />

      <div className="flex items-end gap-2 max-w-3xl mx-auto w-full">
        {/* Paperclip attach button */}
        <button
          type="button"
          aria-label="Attach document"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className={cn(
            "relative inline-flex items-center justify-center",
            "min-w-[44px] min-h-[44px] rounded-lg shrink-0",
            "text-muted-foreground hover:text-foreground hover:bg-muted",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "cursor-pointer",
            "motion-safe:transition-colors motion-safe:duration-150",
          )}
        >
          <Paperclip className="size-5" aria-hidden="true" />
        </button>

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
