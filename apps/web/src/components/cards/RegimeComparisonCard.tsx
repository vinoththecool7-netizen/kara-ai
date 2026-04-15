"use client";

import { useId, useState } from "react";
import { ArrowRightLeft, Award, ChevronDown, ChevronUp, Trophy } from "lucide-react";
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
import { formatCompactINR, formatINR, formatPercent } from "@/lib/format";
import type { RegimeComparison, SlabBreakdown, TaxBreakdown } from "@/types/chat";

interface RegimeComparisonCardProps {
  comparison: RegimeComparison;
}

const regimeName = (r: "old" | "new"): string =>
  r === "old" ? "Old Regime" : "New Regime";

export function RegimeComparisonCard({ comparison }: RegimeComparisonCardProps) {
  const [detailOpen, setDetailOpen] = useState(false);
  const titleId = useId();
  const detailId = useId();

  const { old_regime, new_regime, recommended_regime, savings, breakeven_deductions, explanation } =
    comparison;

  const winner = savings === 0 ? "tie" : recommended_regime;
  const badgeLabel =
    winner === "tie" ? "Tied" : `${regimeName(winner)} wins`;

  return (
    <div className="animate-in fade-in duration-200 motion-reduce:animate-none">
      <Card className="w-full max-w-xl bg-card" aria-labelledby={titleId}>
        {/* Header */}
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle id={titleId} className="text-lg flex items-center gap-2">
                <ArrowRightLeft className="size-4" aria-hidden="true" />
                Regime Comparison
              </CardTitle>
              <CardDescription className="text-xs">
                FY {old_regime.financial_year} · AY {old_regime.assessment_year}
              </CardDescription>
            </div>
            <Badge
              variant={winner === "tie" ? "secondary" : "default"}
              className="ml-2 shrink-0"
            >
              {badgeLabel}
            </Badge>
          </div>
        </CardHeader>

        {/* Winner tiles */}
        <CardContent className="pb-3">
          <dl className="grid grid-cols-2 gap-2 sm:gap-3 mb-4">
            <RegimeTile
              label="Old Regime"
              value={old_regime.total_tax_payable}
              winner={winner === "old"}
            />
            <RegimeTile
              label="New Regime"
              value={new_regime.total_tax_payable}
              winner={winner === "new"}
            />
          </dl>

          {/* Horizontal bar comparison */}
          <ComparisonBars old={old_regime} next={new_regime} />

          {/* Recommendation callout */}
          <RecommendationCallout
            winner={winner}
            savings={savings}
            breakevenDeductions={breakeven_deductions}
            explanation={explanation}
          />
        </CardContent>

        {/* Collapsible slab detail */}
        <div
          id={detailId}
          role="region"
          aria-label="Slab breakdown by regime"
          className={cn(
            "grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none",
            detailOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
          )}
        >
          <div className="overflow-hidden">
            <CardContent className="border-t border-border pt-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <RegimeSlabColumn label="Old Regime" breakdown={old_regime} />
                <RegimeSlabColumn label="New Regime" breakdown={new_regime} />
              </div>
            </CardContent>
          </div>
        </div>

        {/* Toggle */}
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
            {detailOpen ? "Hide slab breakdown" : "Show slab breakdown"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function RegimeTile({
  label,
  value,
  winner,
}: {
  label: string;
  value: number;
  winner: boolean;
}) {
  const fullValue = formatINR(value);
  return (
    <div
      className={cn(
        "rounded-md border border-border/50 bg-muted/30 p-3 min-h-[88px]",
        "flex flex-col justify-center",
        winner && "ring-2 ring-kara-accent",
      )}
      title={fullValue}
      aria-label={`${label} total tax payable: ${fullValue}`}
    >
      <dt className="text-xs text-muted-foreground flex items-center gap-1.5">
        {winner && <Trophy className="size-3.5 text-kara-accent" aria-hidden="true" />}
        {label}
      </dt>
      <dd className="text-base sm:text-lg font-semibold tabular-nums text-foreground mt-1">
        {formatINR(value)}
      </dd>
    </div>
  );
}

interface ComparisonRow {
  key: keyof Pick<
    TaxBreakdown,
    "gross_total_income" | "total_deductions" | "taxable_income" | "total_tax_payable"
  >;
  label: string;
}

const COMPARISON_ROWS: ComparisonRow[] = [
  { key: "gross_total_income", label: "Gross Income" },
  { key: "total_deductions", label: "Total Deductions" },
  { key: "taxable_income", label: "Taxable Income" },
  { key: "total_tax_payable", label: "Total Tax" },
];

function ComparisonBars({ old: oldR, next }: { old: TaxBreakdown; next: TaxBreakdown }) {
  return (
    <figure className="space-y-3 mb-4">
      <figcaption className="sr-only">
        Side-by-side comparison of old and new regime totals
      </figcaption>
      <ul role="list" className="space-y-3">
        {COMPARISON_ROWS.map((row) => {
          const oldVal = oldR[row.key];
          const newVal = next[row.key];
          const max = Math.max(oldVal, newVal) || 1;
          return (
            <li key={row.key} className="sm:flex sm:items-center sm:gap-3">
              <div className="text-xs font-medium text-muted-foreground sm:w-40 sm:shrink-0 mb-1 sm:mb-0">
                {row.label}
              </div>
              <div className="flex-1 space-y-1">
                <Bar
                  regimeLabel="Old"
                  value={oldVal}
                  max={max}
                  colorClass="bg-kara-primary"
                />
                <Bar
                  regimeLabel="New"
                  value={newVal}
                  max={max}
                  colorClass="bg-kara-accent"
                />
              </div>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

function Bar({
  regimeLabel,
  value,
  max,
  colorClass,
}: {
  regimeLabel: string;
  value: number;
  max: number;
  colorClass: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const full = formatINR(value);
  return (
    <div
      className="flex items-center gap-2"
      title={`${regimeLabel}: ${full}`}
      aria-label={`${regimeLabel} regime: ${full}`}
    >
      <span className="text-[10px] text-muted-foreground w-6 shrink-0 uppercase tracking-wide">
        {regimeLabel}
      </span>
      <div className="flex-1 bg-muted/40 rounded-full overflow-hidden h-3">
        <div
          className={cn("h-3 rounded-full transition-[width] duration-300 motion-reduce:transition-none", colorClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-foreground w-16 text-right shrink-0">
        {formatCompactINR(value)}
      </span>
    </div>
  );
}

function RecommendationCallout({
  winner,
  savings,
  breakevenDeductions,
  explanation,
}: {
  winner: "old" | "new" | "tie";
  savings: number;
  breakevenDeductions: number;
  explanation: string;
}) {
  const savingsFull = formatINR(savings);
  return (
    <div className="rounded-md border border-kara-accent/30 bg-kara-accent/5 p-3 space-y-1.5">
      <p
        className="text-sm font-medium text-foreground flex items-center gap-2"
        aria-label={
          winner === "tie"
            ? "Both regimes result in the same tax"
            : `${regimeName(winner)} saves ${savingsFull}`
        }
      >
        <Award className="size-4 text-kara-accent shrink-0" aria-hidden="true" />
        {winner === "tie" ? (
          <span>Both regimes result in the same tax</span>
        ) : (
          <span>
            <strong className="font-semibold">{regimeName(winner)}</strong> saves{" "}
            <span className="tabular-nums">{formatINR(savings)}</span>
          </span>
        )}
      </p>
      {breakevenDeductions > 0 && (
        <p className="text-xs text-muted-foreground">
          Breakeven deductions:{" "}
          <span className="tabular-nums">{formatINR(breakevenDeductions)}</span>
        </p>
      )}
      {explanation && (
        <p className="text-xs text-muted-foreground leading-relaxed">{explanation}</p>
      )}
    </div>
  );
}

function RegimeSlabColumn({
  label,
  breakdown,
}: {
  label: string;
  breakdown: TaxBreakdown;
}) {
  const deductionCount = breakdown.deductions_applied.length;
  return (
    <div className="space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
        {label}
      </h4>
      {breakdown.slab_breakdown.length > 0 ? (
        <MiniSlabTable slabs={breakdown.slab_breakdown} caption={`${label} slab breakdown`} />
      ) : (
        <p className="text-xs text-muted-foreground">No slab tax applicable.</p>
      )}
      <p className="text-xs text-muted-foreground">
        {deductionCount} deduction{deductionCount === 1 ? "" : "s"} applied ·{" "}
        <span className="tabular-nums">{formatINR(breakdown.total_deductions)}</span>
      </p>
    </div>
  );
}

function MiniSlabTable({ slabs, caption }: { slabs: SlabBreakdown[]; caption: string }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <table className="w-full text-xs tabular-nums border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-border">
          <tr>
            <th className="text-left text-muted-foreground font-medium py-1">Slab</th>
            <th className="text-right text-muted-foreground font-medium py-1">Rate</th>
            <th className="text-right text-muted-foreground font-medium py-1">Tax</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {slabs.map((slab, idx) => (
            <tr key={idx}>
              <td className="py-1 text-muted-foreground">
                {formatCompactINR(slab.lower)}
                {" – "}
                {slab.upper >= 99_99_99_999 ? "∞" : formatCompactINR(slab.upper)}
              </td>
              <td className="text-right py-1">{formatPercent(slab.rate, 0)}</td>
              <td className="text-right py-1 font-semibold">
                {formatCompactINR(slab.tax_in_slab)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
