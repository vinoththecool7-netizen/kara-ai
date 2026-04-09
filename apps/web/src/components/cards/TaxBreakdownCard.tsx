"use client";

import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatINR, formatPercent } from "@/lib/format";
import type { TaxBreakdown, DeductionResult, SlabBreakdown } from "@/types/chat";
import { cn } from "@/lib/utils";

interface TaxBreakdownCardProps {
  breakdown: TaxBreakdown;
}

export function TaxBreakdownCard({ breakdown }: TaxBreakdownCardProps) {
  return (
    <div className="animate-in fade-in duration-200 motion-reduce:animate-none">
      <Card className="w-full bg-card">
        {/* Header */}
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-lg">Tax Computation</CardTitle>
              <CardDescription className="text-xs">
                For FY {breakdown.financial_year} · AY {breakdown.assessment_year}
              </CardDescription>
            </div>
            <Badge variant={breakdown.regime === "new" ? "default" : "secondary"} className="ml-2">
              {breakdown.regime === "new" ? "New Regime" : "Old Regime"}
            </Badge>
          </div>
        </CardHeader>

        {/* Content */}
        <CardContent className="space-y-3 pb-3">
          {/* Income Section */}
          <div className="space-y-1.5">
            <MoneyRow label="Gross Salary" value={breakdown.gross_salary} />
            <MoneyRow label="Less: Standard Deduction" value={-breakdown.standard_deduction} />
            <MoneyRow label="Net Salary" value={breakdown.net_salary} bold />

            {breakdown.house_property_income > 0 && (
              <MoneyRow label="House Property Income" value={breakdown.house_property_income} />
            )}
            {breakdown.business_income > 0 && (
              <MoneyRow label="Business Income" value={breakdown.business_income} />
            )}
            {breakdown.capital_gains_income > 0 && (
              <MoneyRow label="Capital Gains" value={breakdown.capital_gains_income} />
            )}
            {breakdown.other_income > 0 && (
              <MoneyRow label="Other Income" value={breakdown.other_income} />
            )}

            <div className="border-t border-border my-2" />
            <MoneyRow label="Gross Total Income" value={breakdown.gross_total_income} bold className="text-base" />
          </div>

          {/* Deductions Section */}
          {breakdown.deductions_applied.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium mt-4 mb-2">Deductions</h4>
              {breakdown.deductions_applied.map((ded, idx) => (
                <DeductionRow key={idx} deduction={ded} />
              ))}
              <div className="border-t border-border my-2" />
              <MoneyRow label="Total Deductions" value={-breakdown.total_deductions} />
              <MoneyRow label="Taxable Income" value={breakdown.taxable_income} bold className="text-base" />
            </div>
          )}

          {/* Tax Computation Section */}
          {breakdown.slab_breakdown.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium mt-4 mb-2">Tax on Income</h4>
              <SlabTable slabs={breakdown.slab_breakdown} />
              <MoneyRow label="Tax on Normal Income" value={breakdown.tax_on_normal_income} bold />

              {breakdown.tax_on_special_rates > 0 && (
                <MoneyRow label="Tax on Special Rates (LTCG/STCG)" value={breakdown.tax_on_special_rates} />
              )}
            </div>
          )}

          {/* Adjustments Section */}
          <div className="space-y-1.5">
            <h4 className="text-xs uppercase tracking-wide text-muted-foreground font-medium mt-4 mb-2">Adjustments</h4>
            <MoneyRow label="Total Tax Before Surcharge" value={breakdown.total_tax_before_surcharge} bold />

            {breakdown.surcharge_amount > 0 && (
              <MoneyRow
                label={`Surcharge (${formatPercent(breakdown.surcharge_rate, 0)})`}
                value={breakdown.surcharge_amount}
              />
            )}
            {breakdown.marginal_relief_surcharge > 0 && (
              <MoneyRow label="Less: Marginal Relief (Surcharge)" value={-breakdown.marginal_relief_surcharge} />
            )}

            <MoneyRow
              label={`Health & Education Cess (${formatPercent(breakdown.cess_rate, 0)})`}
              value={breakdown.cess_amount}
            />

            {breakdown.rebate_87a > 0 && (
              <MoneyRow label="Less: Rebate u/s 87A" value={-breakdown.rebate_87a} />
            )}
            {breakdown.marginal_relief_87a > 0 && (
              <MoneyRow label="Less: Marginal Relief (87A)" value={-breakdown.marginal_relief_87a} />
            )}
          </div>
        </CardContent>

        {/* Footer — Net Tax Payable */}
        <CardFooter className="border-t border-border pt-4">
          <div className="w-full flex justify-between items-baseline">
            <span className="text-sm font-medium text-muted-foreground">Net Tax Payable</span>
            <span className="text-2xl font-bold text-kara-primary tabular-nums">{formatINR(breakdown.total_tax_payable)}</span>
          </div>
        </CardFooter>

        {/* Effective Rate Badge */}
        <div className="px-6 pb-4 flex justify-end">
          <Badge variant="outline" className="text-xs">
            {formatPercent(breakdown.effective_tax_rate)} effective rate
          </Badge>
        </div>
      </Card>
    </div>
  );
}

/** Money row helper: label + formatted value */
function MoneyRow({
  label,
  value,
  bold = false,
  className,
}: {
  label: string;
  value: number;
  bold?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex justify-between items-baseline text-sm gap-2", className)}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("tabular-nums", bold ? "font-semibold" : "font-medium")}>
        {value < 0 ? `−${formatINR(-value)}` : formatINR(value)}
      </dd>
    </div>
  );
}

/** Deduction row: section + note + claimed/allowed */
function DeductionRow({ deduction }: { deduction: DeductionResult }) {
  return (
    <div className="flex justify-between items-start text-xs gap-2">
      <div className="flex-1">
        <dt className="font-mono text-muted-foreground">{deduction.section}</dt>
        <dd className="text-xs text-muted-foreground/75">{deduction.note}</dd>
      </div>
      <div className="text-right">
        {deduction.claimed !== deduction.allowed ? (
          <div className="tabular-nums">
            <span className="line-through text-muted-foreground/60">{formatINR(deduction.claimed)}</span>
            <span className="block font-medium">{formatINR(deduction.allowed)}</span>
          </div>
        ) : (
          <span className="font-medium tabular-nums">{formatINR(deduction.allowed)}</span>
        )}
      </div>
    </div>
  );
}

/** Slab breakdown table */
function SlabTable({ slabs }: { slabs: SlabBreakdown[] }) {
  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <table className="w-full text-xs tabular-nums border-collapse">
        <thead className="border-b border-border">
          <tr>
            <th className="text-left text-muted-foreground font-medium py-1">Range</th>
            <th className="text-right text-muted-foreground font-medium py-1">Rate</th>
            <th className="text-right text-muted-foreground font-medium py-1">Taxable</th>
            <th className="text-right text-muted-foreground font-medium py-1">Tax</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {slabs.map((slab, idx) => (
            <tr key={idx}>
              <td className="py-1 text-muted-foreground">
                {formatINR(slab.lower)}
                {" – "}
                {slab.upper > 99_99_999 ? "∞" : formatINR(slab.upper)}
              </td>
              <td className="text-right py-1">{formatPercent(slab.rate, 0)}</td>
              <td className="text-right py-1">{formatINR(slab.taxable_in_slab)}</td>
              <td className="text-right py-1 font-semibold">{formatINR(slab.tax_in_slab)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
