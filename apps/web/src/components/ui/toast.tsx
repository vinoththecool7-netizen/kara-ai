"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { dismiss, subscribe, type Toast } from "@/hooks/useToast";

const icons = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
} as const;

const variantStyles = {
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  info: "border-border bg-background text-foreground",
} as const;

export function Toaster() {
  const [toasts, setToasts] = useState<readonly Toast[]>([]);

  useEffect(() => subscribe(setToasts), []);

  useEffect(() => {
    if (toasts.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        const newest = toasts[toasts.length - 1];
        if (newest) dismiss(newest.id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toasts]);

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none"
    >
      {toasts.map((t) => {
        const Icon = icons[t.variant];
        return (
          <div
            key={t.id}
            role="status"
            aria-live={t.variant === "error" ? "assertive" : "polite"}
            className={cn(
              "pointer-events-auto border rounded-lg px-4 py-3 shadow-lg flex items-start gap-3 text-sm",
              "animate-in slide-in-from-right-5 fade-in duration-200 motion-reduce:animate-none",
              variantStyles[t.variant],
            )}
          >
            <Icon className="size-5 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="flex-1 min-w-0">
              <p className="font-medium">{t.title}</p>
              {t.description && (
                <p className="opacity-80 mt-0.5">{t.description}</p>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              <X className="size-3.5" aria-hidden="true" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}
