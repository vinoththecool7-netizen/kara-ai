"use client";

import { useId } from "react";
import { ArrowRight, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatCompactINR, formatINR, formatPercent } from "@/lib/format";
import type { CapitalGainsDetail } from "@/types/chat";

// ---------------------------------------------------------------------------
// Module-level maps
// ---------------------------------------------------------------------------

const ASSET_LABELS: Record<string, string> = {
  listed_equity: "Listed Equity",
  equity_mf: "Equity MF",
  debt_mf: "Debt MF",
  property: "Property",
  gold: "Gold",
  unlisted_shares: "Unlisted Shares",
  vda_crypto: "Crypto / VDA",
};

const GAIN_TYPE_LABELS: Record<string, string> = {
  short_term: "Short Term",
  long_term: "Long Term",
};

const ASSET_BADGE_CLS: Record<string, string> = {
  listed_equity:
    "bg-kara-primary/10 text-kara-primary border-transparent",
  equity_mf:
    "bg-kara-primary/10 text-kara-primary border-transparent",
  debt_mf:
    "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300 border-transparent",
  property:
    "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 border-transparent",
  gold:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300 border-transparent",
  unlisted_shares:
    "bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-300 border-transparent",
  vda_crypto:
    "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300 border-transparent",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CapitalGainsCardProps {
  gains: CapitalGainsDetail[];
}

export function CapitalGainsCard({ gains }: CapitalGainsCardProps) {
  const titleId = useId();

  if (gains.length === 0) return null;

  const totalGain = gains.reduce((s, g) => s + g.total_gain, 0);
  const totalTax = gains.reduce((s, g) => s + g.tax_amount, 0);
  const totalExempt = gains.reduce((s, g) => s + g.exempt_amount, 0);

  return (
    <div className="animate-in fade-in duration-200 motion-reduce:animate-none">
      <Card className="w-full max-w-xl bg-card" aria-labelledby={titleId}>
        {/* Header */}
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle id={titleId} className="text-lg flex items-center gap-2">
                <TrendingUp className="size-4" aria-hidden="true" />
                Capital Gains Summary
              </CardTitle>
              <CardDescription className="text-xs">
                {gains.length} transaction{gains.length === 1 ? "" : "s"}
              </CardDescription>
            </div>
            <Badge variant="default" className="ml-2 shrink-0">
              {formatCompactINR(totalTax)} tax
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="pb-3 space-y-4">
          {/* Summary tiles */}
          <dl
            className={cn(
              "grid gap-2 sm:gap-3",
              totalExempt > 0 ? "grid-cols-3" : "grid-cols-2",
            )}
          >
            <SummaryTile
              label="Total Gain"
              value={totalGain}
              negative={totalGain < 0}
            />
            <SummaryTile label="Total Tax" value={totalTax} />
            {totalExempt > 0 && (
              <SummaryTile label="Total Exempt" value={totalExempt} />
            )}
          </dl>

          {/* Transaction list */}
          <div className="space-y-3">
            {gains.map((gain, idx) => (
              <TransactionItem key={idx} gain={gain} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function SummaryTile({
  label,
  value,
  negative,
}: {
  label: string;
  value: number;
  negative?: boolean;
}) {
  const fullValue = formatINR(value);
  return (
    <div
      className="rounded-md border border-border/50 bg-muted/30 p-3 min-h-[72px] flex flex-col justify-center"
      title={fullValue}
      aria-label={`${label}: ${fullValue}`}
    >
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "text-base font-semibold tabular-nums mt-1",
          negative ? "text-destructive" : "text-foreground",
        )}
        title={fullValue}
        aria-label={`${label}: ${fullValue}`}
      >
        {fullValue}
      </dd>
    </div>
  );
}

function TransactionItem({ gain }: { gain: CapitalGainsDetail }) {
  const assetBadgeCls =
    ASSET_BADGE_CLS[gain.asset_class] ??
    "bg-muted text-muted-foreground border-transparent";

  const gainTypeCls =
    gain.gain_type === "long_term"
      ? "text-kara-accent bg-kara-accent/10 border-transparent"
      : "text-kara-cta bg-kara-cta/10 border-transparent";

  const isLoss = gain.total_gain < 0;

  return (
    <div className="border border-border/50 rounded-lg p-3 space-y-2">
      {/* Badge row */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge className={cn("text-xs shrink-0", assetBadgeCls)}>
          {ASSET_LABELS[gain.asset_class] ?? gain.asset_class}
        </Badge>
        <Badge className={cn("text-xs shrink-0", gainTypeCls)}>
          {GAIN_TYPE_LABELS[gain.gain_type] ?? gain.gain_type}
        </Badge>
        {gain.section && (
          <span className="text-xs text-muted-foreground font-mono">
            §{gain.section}
          </span>
        )}
      </div>

      {/* Flow row */}
      <div className="flex items-center gap-1.5 text-sm tabular-nums">
        <span>{formatINR(gain.purchase_price)}</span>
        <ArrowRight className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
        <span>{formatINR(gain.sale_price)}</span>
      </div>

      {/* Computation dl grid */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
        <dt className="text-muted-foreground">
          {isLoss ? "Loss" : "Gain"}
        </dt>
        <dd
          className={cn("tabular-nums text-right", isLoss && "text-destructive")}
          title={formatINR(gain.total_gain)}
          aria-label={`${isLoss ? "Loss" : "Gain"}: ${formatINR(gain.total_gain)}`}
        >
          {formatINR(gain.total_gain)}{isLoss && " (Loss)"}
        </dd>

        {gain.exempt_amount !== 0 && (
          <>
            <dt className="text-muted-foreground">Exempt</dt>
            <dd
              className="tabular-nums text-right"
              title={formatINR(gain.exempt_amount)}
              aria-label={`Exempt: ${formatINR(gain.exempt_amount)}`}
            >
              {formatINR(gain.exempt_amount)}
            </dd>
          </>
        )}

        <dt className="text-muted-foreground">Taxable</dt>
        <dd
          className="tabular-nums text-right"
          title={formatINR(gain.taxable_gain)}
          aria-label={`Taxable: ${formatINR(gain.taxable_gain)}`}
        >
          {formatINR(gain.taxable_gain)}
        </dd>

        <dt className="text-muted-foreground">Rate</dt>
        <dd
          className="tabular-nums text-right"
          aria-label={`Rate: ${gain.tax_rate === 0 ? "Slab rate" : formatPercent(gain.tax_rate)}`}
        >
          {gain.tax_rate === 0 ? "Slab rate" : formatPercent(gain.tax_rate)}
        </dd>

        <dt className="text-muted-foreground">Tax</dt>
        <dd
          className="tabular-nums text-right font-semibold"
          title={formatINR(gain.tax_amount)}
          aria-label={`Tax: ${formatINR(gain.tax_amount)}`}
        >
          {formatINR(gain.tax_amount)}
        </dd>
      </dl>

      {/* Meta */}
      <p className="text-xs text-muted-foreground">
        Held: {gain.holding_months} month{gain.holding_months === 1 ? "" : "s"}
      </p>

      {/* Note */}
      {gain.note && (
        <p className="text-xs text-muted-foreground mt-1">{gain.note}</p>
      )}
    </div>
  );
}
