"use client";

import { computeWaterfallSteps } from "@/lib/waterfall";
import { formatCompactINR } from "@/lib/format";
import type { TaxBreakdown } from "@/types/chat";
import { useId } from "react";
import { cn } from "@/lib/utils";

interface WaterfallChartProps {
  breakdown: TaxBreakdown;
  className?: string;
}

export function WaterfallChart({ breakdown, className }: WaterfallChartProps) {
  const steps = computeWaterfallSteps(breakdown);
  const chartId = useId();
  const titleId = `${chartId}-title`;
  const descId = `${chartId}-desc`;

  // SVG constants
  const viewBoxWidth = 360;
  const viewBoxHeight = 220;
  const paddingX = 16;
  const paddingY = 16;
  const chartWidth = viewBoxWidth - 2 * paddingX;
  const chartHeight = viewBoxHeight - 2 * paddingY;
  const barWidth = (chartWidth - (steps.length - 1) * 8) / steps.length;
  const barGap = 8;

  // Two scales: income and tax
  const incomeMax = breakdown.gross_total_income * 1.1;
  const taxMax = breakdown.total_tax_payable * 1.1;

  // Helper to convert value to Y position
  const getY = (value: number, kind: "income" | "tax") => {
    const scale = kind === "income" ? incomeMax : taxMax;
    const scaleHeight = kind === "income" ? chartHeight * 0.35 : chartHeight * 0.55;
    const offset = kind === "income" ? paddingY : paddingY + chartHeight * 0.35 + 10;
    return offset + scaleHeight - (value / scale) * scaleHeight;
  };

  // Helper to get bar color class based on kind
  const getBarColor = (kind: string) => {
    switch (kind) {
      case "income":
      case "rebate":
        return "fill-kara-accent";  // emerald
      case "deduction":
        return "fill-destructive";  // red
      case "tax":
        return "fill-kara-cta";     // orange
      default:
        return "fill-foreground";
    }
  };

  // Build SVG bars and labels
  const barElements = steps.map((step, idx) => {
    const x = paddingX + idx * (barWidth + barGap);
    const kind = step.isTotal ? "income" : step.kind;
    const y = getY(Math.abs(step.value), kind === "deduction" ? "income" : kind === "tax" ? "tax" : "income");
    const h = Math.abs((Math.abs(step.value) / (kind === "tax" ? taxMax : incomeMax)) * (kind === "tax" ? chartHeight * 0.55 : chartHeight * 0.35));

    return (
      <g key={idx}>
        {/* Bar */}
        <rect
          x={x}
          y={y}
          width={barWidth}
          height={Math.max(h, 1)}
          rx="4"
          className={cn("wf-bar transition-all duration-300", getBarColor(kind))}
          style={{ "--i": idx } as React.CSSProperties}
        />
        {/* Value label above bar */}
        <text
          x={x + barWidth / 2}
          y={y - 4}
          textAnchor="middle"
          className="text-[9px] fill-foreground font-semibold"
        >
          {formatCompactINR(step.value)}
        </text>
        {/* Step label below baseline */}
        <text
          x={x + barWidth / 2}
          y={viewBoxHeight - paddingY + 12}
          textAnchor="middle"
          className="text-[8px] fill-muted-foreground"
        >
          {step.label.length > 12 ? step.label.substring(0, 10) + "…" : step.label}
        </text>
      </g>
    );
  });

  // Summary text for figcaption
  const summaryText = `Waterfall: From ₹${breakdown.gross_total_income.toLocaleString("en-IN")} gross income, less ₹${breakdown.total_deductions.toLocaleString("en-IN")} deductions, taxable ₹${breakdown.taxable_income.toLocaleString("en-IN")}, plus ₹${(breakdown.total_tax_payable - breakdown.rebate_87a).toLocaleString("en-IN")} in tax components, minus ₹${breakdown.rebate_87a.toLocaleString("en-IN")} rebate, net tax payable ₹${breakdown.total_tax_payable.toLocaleString("en-IN")} (${(breakdown.effective_tax_rate * 100).toFixed(1)}% effective rate).`;

  return (
    <figure className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-auto max-h-56 block"
        role="img"
        aria-labelledby={titleId}
        aria-describedby={descId}
      >
        <title id={titleId}>Tax Computation Waterfall</title>
        <desc id={descId}>{summaryText}</desc>

        {/* Baseline axis */}
        <line
          x1={paddingX}
          y1={viewBoxHeight - paddingY}
          x2={viewBoxWidth - paddingX}
          y2={viewBoxHeight - paddingY}
          className="stroke-border stroke-[1]"
        />

        {/* Zone labels */}
        <text
          x={paddingX + chartWidth * 0.25}
          y={paddingY + 8}
          textAnchor="middle"
          className="text-[9px] fill-muted-foreground uppercase tracking-wide font-medium"
        >
          Income
        </text>
        <text
          x={paddingX + chartWidth * 0.75}
          y={paddingY + chartHeight * 0.35 + 12}
          textAnchor="middle"
          className="text-[9px] fill-muted-foreground uppercase tracking-wide font-medium"
        >
          Tax
        </text>

        {/* Connector lines between bars */}
        {steps.map((step, idx) => {
          if (idx === steps.length - 1) return null;
          const x1 = paddingX + idx * (barWidth + barGap) + barWidth;
          const x2 = paddingX + (idx + 1) * (barWidth + barGap);
          const kind = step.isTotal ? "income" : step.kind;
          const y1 = getY(Math.abs(step.value), kind === "deduction" ? "income" : kind === "tax" ? "tax" : "income");
          const nextStep = steps[idx + 1];
          const nextKind = nextStep.isTotal ? "income" : nextStep.kind;
          const y2 = getY(Math.abs(nextStep.value), nextKind === "deduction" ? "income" : nextKind === "tax" ? "tax" : "income");
          return (
            <line
              key={`connector-${idx}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              className="stroke-muted-foreground/40 stroke-[1]"
              strokeDasharray="2 2"
            />
          );
        })}

        {/* Bars + labels */}
        {barElements}
      </svg>

      <figcaption className="sr-only">{summaryText}</figcaption>
    </figure>
  );
}
