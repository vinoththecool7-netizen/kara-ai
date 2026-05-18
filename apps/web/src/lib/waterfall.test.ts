/**
 * Self-contained tests for computeWaterfallSteps.
 * Run: cd apps/web && npx tsx src/lib/waterfall.test.ts
 */
import { computeWaterfallSteps } from "./waterfall";
import type { TaxBreakdown } from "../types/chat";

let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string): void {
  if (condition) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg}`);
  }
}

function assertEqual(actual: unknown, expected: unknown, msg: string): void {
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    console.error(`  FAIL: ${msg} — expected ${expected}, got ${actual}`);
  }
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_BREAKDOWN: TaxBreakdown = {
  regime: "new",
  financial_year: "2025-26",
  assessment_year: "2026-27",
  age_category: "below_60",
  gross_salary: 15_00_000,
  standard_deduction: 75_000,
  net_salary: 14_25_000,
  house_property_income: 0,
  business_income: 0,
  capital_gains_income: 0,
  other_income: 0,
  gross_total_income: 14_25_000,
  deductions_applied: [],
  total_deductions: 0,
  taxable_income: 14_25_000,
  slab_breakdown: [],
  tax_on_normal_income: 1_50_000,
  tax_on_special_rates: 0,
  capital_gains_details: [],
  total_tax_before_surcharge: 1_50_000,
  surcharge_rate: 0,
  surcharge_amount: 0,
  marginal_relief_surcharge: 0,
  cess_rate: 0.04,
  cess_amount: 6_000,
  rebate_87a: 0,
  marginal_relief_87a: 0,
  total_tax_payable: 1_56_000,
  effective_tax_rate: 0.1095,
  computation_steps: [],
};

// ---------------------------------------------------------------------------
// Test 1: Happy path — 15L new regime, no deductions
// ---------------------------------------------------------------------------
console.log("Test 1: Happy path (15L new regime, no deductions)");
{
  const steps = computeWaterfallSteps(BASE_BREAKDOWN);
  // No deductions, no special rates, no surcharge, no rebate → 5 steps
  // Gross, Taxable, Normal Tax, Cess, Net
  assertEqual(steps.length, 5, "should have 5 steps (no deduction/special/surcharge/rebate)");
  assertEqual(steps[0].label, "Gross Total Income", "step 0 label");
  assertEqual(steps[0].isTotal, true, "step 0 isTotal");
  assertEqual(steps[0].value, 14_25_000, "step 0 value");
  assertEqual(steps[1].label, "Taxable Income", "step 1 label (deductions skipped)");
  assertEqual(steps[1].isTotal, true, "step 1 isTotal");
  assertEqual(steps[2].label, "Tax on Normal Income", "step 2 label");
  assertEqual(steps[2].value, 1_50_000, "step 2 value");
  assertEqual(steps[3].label, "Health & Education Cess", "step 3 label");
  assertEqual(steps[3].value, 6_000, "step 3 value");
  assertEqual(steps[4].label, "Net Tax Payable", "step 4 label");
  assertEqual(steps[4].value, 1_56_000, "step 4 value");
  assertEqual(steps[4].isTotal, true, "step 4 isTotal");
}

// ---------------------------------------------------------------------------
// Test 2: With deductions — old regime
// ---------------------------------------------------------------------------
console.log("Test 2: With deductions (old regime)");
{
  const bd: TaxBreakdown = {
    ...BASE_BREAKDOWN,
    regime: "old",
    total_deductions: 2_50_000,
    taxable_income: 11_75_000,
    tax_on_normal_income: 1_12_500,
    total_tax_before_surcharge: 1_12_500,
    cess_amount: 4_500,
    total_tax_payable: 1_17_000,
  };
  const steps = computeWaterfallSteps(bd);
  // Has deductions → 6 steps: Gross, Deductions, Taxable, Normal Tax, Cess, Net
  assertEqual(steps.length, 6, "should have 6 steps (with deductions)");
  assertEqual(steps[1].label, "Less: Deductions", "step 1 is deductions");
  assertEqual(steps[1].value, -2_50_000, "deduction value is negative");
  assertEqual(steps[1].kind, "deduction", "deduction kind");
  assertEqual(steps[2].label, "Taxable Income", "step 2 is taxable income");
  assertEqual(steps[2].value, 11_75_000, "taxable income value");
}

// ---------------------------------------------------------------------------
// Test 3: Zero-skipping — all optional fields zero
// ---------------------------------------------------------------------------
console.log("Test 3: Zero-skipping (minimal breakdown)");
{
  const minimal: TaxBreakdown = {
    ...BASE_BREAKDOWN,
    total_deductions: 0,
    tax_on_special_rates: 0,
    surcharge_amount: 0,
    rebate_87a: 0,
  };
  const steps = computeWaterfallSteps(minimal);
  const labels = steps.map((s) => s.label);
  assert(!labels.includes("Less: Deductions"), "deductions skipped");
  assert(!labels.includes("Tax on Special Rates"), "special rates skipped");
  assert(!labels.includes("Surcharge"), "surcharge skipped");
  assert(!labels.includes("Less: Rebate u/s 87A"), "rebate skipped");
}

// ---------------------------------------------------------------------------
// Test 4: Full breakdown — all fields present
// ---------------------------------------------------------------------------
console.log("Test 4: Full breakdown (all fields present)");
{
  const full: TaxBreakdown = {
    ...BASE_BREAKDOWN,
    total_deductions: 1_50_000,
    taxable_income: 12_75_000,
    tax_on_normal_income: 1_20_000,
    tax_on_special_rates: 30_000,
    surcharge_amount: 15_000,
    cess_amount: 6_600,
    rebate_87a: 0,
    total_tax_payable: 1_71_600,
  };
  const steps = computeWaterfallSteps(full);
  // Has deductions + special rates + surcharge → 8 steps (no rebate)
  assertEqual(steps.length, 8, "should have 8 steps");
  assertEqual(steps[4].label, "Tax on Special Rates", "special rates present");
  assertEqual(steps[5].label, "Surcharge", "surcharge present");
}

// ---------------------------------------------------------------------------
// Test 5: Rebate regime — tax zeroed out by 87A
// ---------------------------------------------------------------------------
console.log("Test 5: Rebate regime (tax zeroed by 87A)");
{
  const rebated: TaxBreakdown = {
    ...BASE_BREAKDOWN,
    gross_total_income: 7_00_000,
    taxable_income: 7_00_000,
    tax_on_normal_income: 25_000,
    cess_amount: 1_000,
    rebate_87a: 26_000,
    total_tax_payable: 0,
  };
  const steps = computeWaterfallSteps(rebated);
  const rebateStep = steps.find((s) => s.label === "Less: Rebate u/s 87A");
  assert(rebateStep !== undefined, "rebate step present");
  assertEqual(rebateStep!.kind, "rebate", "rebate kind");
  assertEqual(rebateStep!.value, -26_000, "rebate is negative");
  const netStep = steps[steps.length - 1];
  assertEqual(netStep.label, "Net Tax Payable", "last step is net tax");
  assertEqual(netStep.value, 0, "net tax is zero");
}

// ---------------------------------------------------------------------------
// Test 6: Cumulative integrity on tax side
// ---------------------------------------------------------------------------
console.log("Test 6: Cumulative integrity");
{
  const full: TaxBreakdown = {
    ...BASE_BREAKDOWN,
    total_deductions: 1_50_000,
    taxable_income: 12_75_000,
    tax_on_normal_income: 1_20_000,
    tax_on_special_rates: 30_000,
    surcharge_amount: 15_000,
    cess_amount: 6_600,
    rebate_87a: 0,
    total_tax_payable: 1_71_600,
  };
  const steps = computeWaterfallSteps(full);
  // Walk tax steps and verify cumulative = prev_cumulative + value
  const taxSteps = steps.filter((s) => !s.isTotal && (s.kind === "tax" || s.kind === "rebate"));
  let running = 0;
  for (const step of taxSteps) {
    running += step.value;
    assertEqual(step.cumulative, running, `cumulative for "${step.label}"`);
  }
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
} else {
  console.log("OK");
}
