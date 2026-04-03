"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

const DOTS: { delay: string }[] = [
  { delay: "0ms" },
  { delay: "150ms" },
  { delay: "300ms" },
];

export function TypingIndicator() {
  return (
    <div
      className={cn("flex flex-row items-end gap-2")}
      role="status"
      aria-label="Kara is thinking"
    >
      {/* Kara avatar */}
      <Avatar className="h-8 w-8 bg-kara-primary text-white shrink-0">
        <AvatarFallback className="bg-kara-primary text-white text-sm font-semibold">
          K
        </AvatarFallback>
      </Avatar>

      {/* Bubble */}
      <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex items-center gap-1">
          {DOTS.map(({ delay }, i) => (
            <span
              key={i}
              className="inline-block h-2 w-2 rounded-full bg-foreground/40 animate-bounce"
              style={{ animationDelay: delay }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
