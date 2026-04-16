"use client";

import { useId, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Lock,
  PiggyBank,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatCompactINR, formatINR } from "@/lib/format";
import type { OptimizationResult, OptimizationSuggestion } from "@/types/chat";

interface DeductionGapCardProps {
  optimization: OptimizationResult;
}

interface SectionRow {
  label: string;
  used: number;
  remaining: number;
}

function progressColorClass(pct: number): string {
  if (pct >= 80) return "bg-kara-accent";
  if (pct >= 50) return "bg-amber-500";
  return "bg-destructive";
}

export function DeductionGapCard({ optimization }: DeductionGapCardProps) {
  const [detailOpen, setDetailOpen] = useState(false);
  const titleId = useId();
  const detailId = useId();

  const {
    current_tax,
    optimized_tax,
    total_potential_saving,
    suggestions,
    section_80c_used,
    section_80c_remaining,
    section_80d_used,
    section_80d_remaining,
    section_80ccd_1b_used,
    section_80ccd_1b_remaining,
  } = optimization;

  const sectionRows: SectionRow[] = [
    { label: "80C", used: section_80c_used, remaining: section_80c_remaining },
    { label: "80D", used: section_80d_used, remaining: section_80d_remaining },
    {
      label: "80CCD(1B)",
      used: section_80ccd_1b_used,
      remaining: section_80ccd_1b_remaining,
    },
  ].filter((row) => row.used + row.remaining > 0);

  const hasSavings = total_potential_saving > 0;
  const hasSuggestions = suggestions.length > 0;

  return (
    <div className="animate-in fade-in duration-200 motion-reduce:animate-none">
      <Card className="w-full max-w-xl bg-card" aria-labelledby={titleId}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle id={titleId} className="text-lg flex items-center gap-2">
                <PiggyBank className="size-4" aria-hidden="true" />
                Tax Saving Opportunities
              </CardTitle>
              <CardDescription className="text-xs">
                Based on your current deductions
              </CardDescription>
            </div>
            <Badge
              variant={hasSavings ? "default" : "secondary"}
              className="ml-2 shrink-0"
            >
              {hasSavings
                ? `Save ${formatCompactINR(total_potential_saving)}`
                : "Fully optimized"}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="pb-3">
          {/* Current vs Optimized tiles */}
          <dl className="grid grid-cols-2 gap-2 sm:gap-3 mb-2">
            <TaxTile label="Current Tax" value={current_tax} />
            <TaxTile label="Optimized Tax" value={optimized_tax} highlight />
          </dl>
          {hasSavings ? (
            <p
              className="text-sm font-semibold text-kara-accent tabular-nums mb-4"
              aria-label={`Potential saving: ${formatINR(total_potential_saving)}`}
            >
              -{formatINR(total_potential_saving)}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground mb-4">No savings</p>
          )}

          {/* Progress bars */}
          {sectionRows.length > 0 && (
            <ul role="list" className="space-y-3">
              {sectionRows.map((row) => {
                const cap = row.used + row.remaining;
                const pct = Math.max(
                  0,
                  Math.min(100, (row.used / cap) * 100),
                );
                const pctDisplay = Math.round(pct);
                const colorClass = progressColorClass(pct);
                const usedFull = formatINR(row.used);
                const capFull = formatINR(cap);
                const remainingFull = formatINR(row.remaining);
                return (
                  <li key={row.label} className="space-y-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs font-medium text-muted-foreground">
                        Section {row.label}
                      </span>
                      <span
                        className="text-xs tabular-nums text-foreground"
                        title={`${usedFull} / ${capFull}`}
                      >
                        {usedFull}
                        <span className="text-muted-foreground"> / </span>
                        {capFull}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all motion-reduce:transition-none",
                          colorClass,
                        )}
                        style={{ width: `${pct}%` }}
                        role="progressbar"
                        aria-valuenow={row.used}
                        aria-valuemin={0}
                        aria-valuemax={cap}
                        aria-label={`${row.label} utilization: ${pctDisplay}%`}
                      />
                    </div>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[10px] text-muted-foreground tabular-nums">
                        {pctDisplay}% utilized
                      </span>
                      <span
                        className="text-[10px] text-muted-foreground tabular-nums"
                        title={`${remainingFull} left`}
                      >
                        {remainingFull} left
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>

        {/* Suggestions section */}
        {hasSuggestions ? (
          <div
            id={detailId}
            role="region"
            aria-label="Investment suggestions"
            className={cn(
              "grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none",
              detailOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
            )}
          >
            <div className="overflow-hidden">
              <CardContent className="border-t border-border pt-3">
                <ul role="list" className="space-y-3">
                  {suggestions.map((s, idx) => (
                    <li key={idx}>
                      <SuggestionRow suggestion={s} />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </div>
          </div>
        ) : (
          <CardContent className="border-t border-border pt-3">
            <p className="text-xs text-muted-foreground">
              No additional investment opportunities found.
            </p>
          </CardContent>
        )}

        {hasSuggestions && (
          <CardFooter className="pt-3 pb-0 flex justify-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDetailOpen(!detailOpen)}
              aria-expanded={detailOpen}
              aria-controls={detailId}
              className="w-full justify-center gap-1.5 min-h-11 touch-manipulation"
            >
              {detailOpen ? (
                <ChevronUp className="size-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="size-4" aria-hidden="true" />
              )}
              {detailOpen ? "Hide investment tips" : "Show investment tips"}
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function TaxTile({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  const fullValue = formatINR(value);
  return (
    <div
      className={cn(
        "rounded-md border border-border/50 bg-muted/30 p-3 min-h-[88px]",
        "flex flex-col justify-center",
        highlight && "ring-2 ring-kara-accent",
      )}
      title={fullValue}
      aria-label={`${label}: ${fullValue}`}
    >
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "text-base sm:text-lg font-semibold tabular-nums mt-1",
          highlight ? "text-kara-accent" : "text-foreground",
        )}
        title={fullValue}
        aria-label={`${label}: ${fullValue}`}
      >
        {fullValue}
      </dd>
    </div>
  );
}

function SuggestionRow({ suggestion }: { suggestion: OptimizationSuggestion }) {
  const {
    section,
    instrument,
    suggested_amount,
    potential_tax_saving,
    lock_in_years,
    expected_return_range,
    note,
  } = suggestion;

  const hasLockIn = lock_in_years !== null && lock_in_years > 0;
  const hasReturnRange = expected_return_range && expected_return_range.length >= 2;
  const hasMeta = hasLockIn || hasReturnRange;

  const investFull = formatINR(suggested_amount);
  const saveFull = formatINR(potential_tax_saving);

  return (
    <div className="border border-border/50 rounded-lg p-3 space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="secondary" className="shrink-0">
          {section}
        </Badge>
        <span className="font-semibold text-sm text-foreground">
          {instrument}
        </span>
      </div>
      <p
        className="text-sm text-foreground flex items-center gap-1.5 flex-wrap"
        aria-label={`Invest ${investFull} to save ${saveFull} in tax`}
      >
        <TrendingUp className="size-3.5 text-kara-accent shrink-0" aria-hidden="true" />
        <span>
          Invest <span className="tabular-nums font-medium">{investFull}</span>
          {" "}→ Save <span className="tabular-nums font-medium text-kara-accent">{saveFull}</span>{" "}
          in tax
        </span>
      </p>
      {hasMeta && (
        <p className="text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
          {hasLockIn && (
            <span className="inline-flex items-center gap-1">
              <Lock className="size-3" aria-hidden="true" />
              {lock_in_years} yr lock-in
            </span>
          )}
          {hasReturnRange && (
            <span className="tabular-nums">
              {expected_return_range[0]}–{expected_return_range[1]}% returns
            </span>
          )}
        </p>
      )}
      {note && (
        <p className="text-xs text-muted-foreground leading-relaxed">{note}</p>
      )}
    </div>
  );
}
