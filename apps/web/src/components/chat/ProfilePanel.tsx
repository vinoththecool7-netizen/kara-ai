"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Trash2, UserRound } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatINR } from "@/lib/format";
import type { ProfileState } from "@/types/chat";

// Slots holding rupee amounts — formatted with Indian grouping.
const MONEY_SLOTS = new Set([
  "gross_salary",
  "business_income",
  "house_property_income",
  "other_income",
  "total_income",
  "total_estimated_tax",
  "purchase_price",
  "sale_price",
  "fmv_31jan2018",
  "hra_exemption",
]);

const SECTION_LABELS: Record<string, string> = {
  section_80c: "Section 80C",
  section_80ccd_1b: "Section 80CCD(1B)",
  section_80ccd_2: "Section 80CCD(2)",
  section_80d: "Section 80D",
  section_80d_parents: "Section 80D (parents)",
  section_80e: "Section 80E",
  section_80g: "Section 80G",
  section_80tta: "Section 80TTA",
  section_24b: "Section 24(b)",
};

function formatSlotLabel(name: string): string {
  if (SECTION_LABELS[name]) return SECTION_LABELS[name];
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatSlotValue(name: string, value: unknown): string {
  if (typeof value === "number" && (MONEY_SLOTS.has(name) || name.startsWith("section_"))) {
    return formatINR(value);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value).replace(/_/g, " ");
}

interface ProfilePanelProps {
  profileState: ProfileState | null;
  onClear: () => void;
}

/**
 * "What Kara knows" — a collapsible summary of the taxpayer facts collected
 * from the conversation and uploaded documents, with a clear-all control.
 */
export function ProfilePanel({ profileState, onClear }: ProfilePanelProps) {
  const [expanded, setExpanded] = useState(false);

  const slots = profileState?.slots ?? {};
  const entries = Object.entries(slots).filter(([, v]) => v !== null && v !== "");
  if (entries.length === 0) return null;

  return (
    <div className="rounded-lg border bg-muted/30">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-controls="profile-panel-details"
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 text-sm text-left",
          "hover:bg-muted/50 rounded-lg transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
        )}
      >
        <UserRound className="size-4 text-kara-primary" aria-hidden="true" />
        <span className="font-medium">What Kara knows</span>
        <span className="text-muted-foreground">
          {entries.length} detail{entries.length === 1 ? "" : "s"}
        </span>
        <span className="ml-auto" aria-hidden="true">
          {expanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </span>
      </button>

      {expanded && (
        <div id="profile-panel-details" className="px-3 pb-3">
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            {entries.map(([name, value]) => (
              <div key={name} className="flex justify-between gap-3">
                <dt className="text-muted-foreground">{formatSlotLabel(name)}</dt>
                <dd className="font-medium tabular-nums">{formatSlotValue(name, value)}</dd>
              </div>
            ))}
          </dl>
          <button
            type="button"
            onClick={onClear}
            className={cn(
              "mt-3 inline-flex items-center gap-1.5 text-xs text-destructive",
              "hover:underline focus-visible:outline-none focus-visible:ring-2",
              "focus-visible:ring-ring/40 rounded",
            )}
          >
            <Trash2 className="size-3.5" aria-hidden="true" />
            Clear these details
          </button>
        </div>
      )}
    </div>
  );
}
