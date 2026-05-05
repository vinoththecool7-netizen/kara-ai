"use client";

import { useState, useId } from "react";
import { ChevronDown, AlertTriangle } from "lucide-react";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatINR } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ParsedDocumentSummary } from "@/types/chat";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DOC_TYPE_LABELS: Record<string, string> = {
  form16: "Form 16",
  ais: "AIS",
  "26as": "26AS",
};

const DOC_TYPE_BADGE: Record<string, string> = {
  form16: "bg-blue-100 text-blue-800",
  ais: "bg-violet-100 text-violet-800",
  "26as": "bg-teal-100 text-teal-800",
};

const KEY_AMOUNT_LABELS: Record<string, string> = {
  gross_salary: "Gross Salary",
  total_tds: "TDS Deducted",
  other_income: "Other Income",
  advance_tax: "Advance Tax",
};

const KEY_AMOUNT_ORDER = ["gross_salary", "total_tds", "other_income", "advance_tax"];

function docTypeLabel(dt: string): string {
  return DOC_TYPE_LABELS[dt] ?? dt.toUpperCase();
}

function badgeClass(dt: string): string {
  return DOC_TYPE_BADGE[dt] ?? "bg-gray-100 text-gray-800";
}

function cardTitle(summary: ParsedDocumentSummary): string {
  const label = docTypeLabel(summary.document_type);
  if (summary.document_type === "form16" && summary.employer_name) {
    return `${label} — ${summary.employer_name}`;
  }
  return label;
}

function cardDescription(summary: ParsedDocumentSummary): string | null {
  const parts: string[] = [];
  if (summary.pan) parts.push(`PAN ${summary.pan}`);
  if (summary.period) parts.push(`FY ${summary.period}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ParsedDocumentCardProps {
  summary: ParsedDocumentSummary;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ParsedDocumentCard({ summary }: ParsedDocumentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const titleId = useId();
  const regionId = useId();

  const title = cardTitle(summary);
  const description = cardDescription(summary);
  const warnings = summary.profile_diff?.warnings ?? [];

  // Only show rows where the value is > 0 and we have a label for them
  const amountRows = KEY_AMOUNT_ORDER.filter(
    (key) => (summary.key_amounts[key] ?? 0) > 0,
  );

  // Additional keys not in the standard order
  const extraKeys = Object.keys(summary.key_amounts).filter(
    (key) => !KEY_AMOUNT_ORDER.includes(key) && (summary.key_amounts[key] ?? 0) > 0,
  );

  const allAmountRows = [...amountRows, ...extraKeys];

  return (
    <div className="animate-in fade-in duration-200 motion-reduce:animate-none">
      <Card
        className="w-full bg-card"
        aria-labelledby={titleId}
      >
        {/* Header */}
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <CardTitle id={titleId} className="text-lg truncate">
                {title}
              </CardTitle>
              {description && (
                <CardDescription className="text-xs mt-0.5">
                  {description}
                </CardDescription>
              )}
            </div>
            <Badge className={cn("shrink-0 text-xs font-medium border-0", badgeClass(summary.document_type))}>
              {docTypeLabel(summary.document_type)}
            </Badge>
          </div>
        </CardHeader>

        {/* Key amounts */}
        {allAmountRows.length > 0 && (
          <CardContent className="pb-3">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2">
              {allAmountRows.map((key) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="text-xs text-muted-foreground">
                    {KEY_AMOUNT_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </dt>
                  <dd className="font-mono tabular-nums text-sm font-semibold text-foreground">
                    {formatINR(summary.key_amounts[key] ?? 0)}
                  </dd>
                </div>
              ))}
            </dl>
          </CardContent>
        )}

        {/* Override warnings */}
        {warnings.length > 0 && (
          <CardContent className="pt-0 pb-3">
            <ul className="space-y-1.5">
              {warnings.map((warning, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400"
                >
                  <AlertTriangle
                    className="size-3.5 shrink-0 mt-0.5"
                    aria-hidden="true"
                  />
                  <span>{warning}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        )}

        {/* Collapsible: fields auto-filled */}
        {summary.fields_filled > 0 && (
          <CardContent className="pt-0 pb-4">
            <button
              type="button"
              onClick={() => setIsExpanded((prev) => !prev)}
              aria-expanded={isExpanded}
              aria-controls={regionId}
              className={cn(
                "relative flex items-center gap-1.5 text-xs text-muted-foreground",
                "rounded px-2 py-2 min-h-[44px] w-full text-left",
                "hover:text-foreground hover:bg-muted cursor-pointer",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                "motion-safe:transition-colors motion-safe:duration-150",
                // Extend tap target
                "before:absolute before:inset-[-4px]",
              )}
            >
              <ChevronDown
                className={cn(
                  "size-3.5 shrink-0",
                  "motion-safe:transition-transform motion-safe:duration-200",
                  isExpanded && "rotate-180",
                )}
                aria-hidden="true"
              />
              <span>
                {summary.fields_filled} field{summary.fields_filled !== 1 ? "s" : ""} auto-filled from this document
              </span>
            </button>

            <div
              id={regionId}
              role="region"
              aria-label={`Auto-filled fields from ${docTypeLabel(summary.document_type)}`}
              className={cn(
                "overflow-hidden text-xs text-muted-foreground",
                "motion-safe:transition-all motion-safe:duration-200",
                isExpanded ? "max-h-96 opacity-100 mt-2" : "max-h-0 opacity-0",
              )}
            >
              <p className="px-2 pb-1">
                Kara extracted {summary.fields_filled} data point{summary.fields_filled !== 1 ? "s" : ""} from this document and updated your tax profile automatically.
                You can override any value by asking Kara directly.
              </p>

              {/* Slots added */}
              {summary.profile_diff &&
                Object.keys(summary.profile_diff.slots_added).length > 0 && (
                  <div className="mt-2 px-2">
                    <p className="font-medium text-foreground mb-1">Slots added:</p>
                    <ul className="space-y-0.5">
                      {Object.entries(summary.profile_diff.slots_added).map(([slot]) => (
                        <li key={slot} className="font-mono">
                          {slot}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* Slots overridden */}
              {summary.profile_diff &&
                Object.keys(summary.profile_diff.slots_overridden).length > 0 && (
                  <div className="mt-2 px-2">
                    <p className="font-medium text-foreground mb-1">Values updated:</p>
                    <ul className="space-y-0.5">
                      {Object.entries(summary.profile_diff.slots_overridden).map(([slot, values]) => (
                        <li key={slot} className="font-mono">
                          {slot}
                          {Array.isArray(values) && values.length >= 2 && (
                            <span className="text-muted-foreground/70">
                              {" "}({String(values[0])} → {String(values[1])})
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
