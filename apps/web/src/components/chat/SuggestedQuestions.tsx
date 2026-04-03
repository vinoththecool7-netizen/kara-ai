"use client";

import { Calculator, Scale, TrendingUp, FileText } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Suggestion {
  text: string;
  Icon: LucideIcon;
}

interface SuggestedQuestionsProps {
  onSelect: (text: string) => void;
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const SUGGESTIONS: Suggestion[] = [
  {
    text: "How much tax do I owe on 15 lakh salary?",
    Icon: Calculator,
  },
  {
    text: "Compare old vs new regime for me",
    Icon: Scale,
  },
  {
    text: "I sold mutual funds worth 8 lakh",
    Icon: TrendingUp,
  },
  {
    text: "What deductions can I claim?",
    Icon: FileText,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SuggestedQuestions({ onSelect }: SuggestedQuestionsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 w-full max-w-md mx-auto">
      {SUGGESTIONS.map(({ text, Icon }) => (
        <button
          key={text}
          type="button"
          onClick={() => onSelect(text)}
          className={cn(
            // Badge-secondary look, sized up
            "inline-flex items-center gap-2 rounded-4xl border border-transparent",
            "bg-secondary text-secondary-foreground",
            "px-3 py-2 text-xs font-medium text-left",
            "min-h-[44px] w-full",
            // Hover transition
            "transition-colors duration-200 hover:bg-secondary/70",
            // Focus ring
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          )}
        >
          <Icon className="size-3.5 shrink-0" aria-hidden="true" />
          <span>{text}</span>
        </button>
      ))}
    </div>
  );
}
