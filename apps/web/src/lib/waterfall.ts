import type { TaxBreakdown } from "@/types/chat";

export type WaterfallStepKind = "income" | "deduction" | "tax" | "rebate" | "total";

export interface WaterfallStep {
  label: string;           // e.g., "Gross Total Income"
  value: number;           // signed delta; positive = add, negative = subtract
  cumulative: number;      // running total AFTER this step
  base: number;            // y-position for floating bar (0 for totals)
  kind: WaterfallStepKind; // determines color
  isTotal: boolean;        // true for Gross, Taxable, Net Tax
}

/**
 * Compute waterfall steps from a TaxBreakdown.
 * Skips zero-value rows (no surcharge, no special rates, etc.).
 * Returns a list of up to 9 steps in sequence.
 */
export function computeWaterfallSteps(breakdown: TaxBreakdown): WaterfallStep[] {
  const steps: WaterfallStep[] = [];
  let cumulativeIncome = 0;

  // 1. Gross Total Income (total)
  steps.push({
    label: "Gross Total Income",
    value: breakdown.gross_total_income,
    cumulative: breakdown.gross_total_income,
    base: 0,
    kind: "income",
    isTotal: true,
  });
  cumulativeIncome = breakdown.gross_total_income;

  // 2. Deductions (deduction)
  if (breakdown.total_deductions > 0) {
    steps.push({
      label: "Less: Deductions",
      value: -breakdown.total_deductions,
      cumulative: breakdown.taxable_income,
      base: breakdown.taxable_income,
      kind: "deduction",
      isTotal: false,
    });
  }

  // 3. Taxable Income (total)
  steps.push({
    label: "Taxable Income",
    value: breakdown.taxable_income,
    cumulative: breakdown.taxable_income,
    base: 0,
    kind: "income",
    isTotal: true,
  });
  let cumulativeTax = 0;

  // 4. Tax on Normal Income (tax)
  if (breakdown.tax_on_normal_income > 0) {
    cumulativeTax += breakdown.tax_on_normal_income;
    steps.push({
      label: "Tax on Normal Income",
      value: breakdown.tax_on_normal_income,
      cumulative: cumulativeTax,
      base: 0,
      kind: "tax",
      isTotal: false,
    });
  }

  // 5. Tax on Special Rates (tax)
  if (breakdown.tax_on_special_rates > 0) {
    cumulativeTax += breakdown.tax_on_special_rates;
    steps.push({
      label: "Tax on Special Rates",
      value: breakdown.tax_on_special_rates,
      cumulative: cumulativeTax,
      base: cumulativeTax - breakdown.tax_on_special_rates,
      kind: "tax",
      isTotal: false,
    });
  }

  // 6. Surcharge (tax)
  if (breakdown.surcharge_amount > 0) {
    cumulativeTax += breakdown.surcharge_amount;
    steps.push({
      label: "Surcharge",
      value: breakdown.surcharge_amount,
      cumulative: cumulativeTax,
      base: cumulativeTax - breakdown.surcharge_amount,
      kind: "tax",
      isTotal: false,
    });
  }

  // 7. Cess (tax)
  cumulativeTax += breakdown.cess_amount;
  steps.push({
    label: "Health & Education Cess",
    value: breakdown.cess_amount,
    cumulative: cumulativeTax,
    base: cumulativeTax - breakdown.cess_amount,
    kind: "tax",
    isTotal: false,
  });

  // 8. Rebate u/s 87A (rebate)
  if (breakdown.rebate_87a > 0) {
    cumulativeTax -= breakdown.rebate_87a;
    steps.push({
      label: "Less: Rebate u/s 87A",
      value: -breakdown.rebate_87a,
      cumulative: cumulativeTax,
      base: cumulativeTax + breakdown.rebate_87a,
      kind: "rebate",
      isTotal: false,
    });
  }

  // 9. Net Tax Payable (total)
  steps.push({
    label: "Net Tax Payable",
    value: breakdown.total_tax_payable,
    cumulative: breakdown.total_tax_payable,
    base: 0,
    kind: "income",  // color as same as other totals (primary color)
    isTotal: true,
  });

  return steps;
}
