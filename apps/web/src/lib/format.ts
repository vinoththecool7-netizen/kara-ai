/**
 * All currency helpers expect integer rupees from the backend.
 */

const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

/**
 * Format integer rupees as ₹12,50,000 (Indian grouping: 2,2,3).
 * Non-finite values return "—".
 */
export function formatINR(amount: number): string {
  if (!Number.isFinite(amount)) return "—";
  return inrFormatter.format(Math.round(amount));
}

/**
 * Format integer as 12,50,000 (no currency symbol).
 */
export function formatIndianNumber(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return numberFormatter.format(Math.round(n));
}

/**
 * Format rate as percentage.
 * @param rate Decimal fraction (0..1), e.g., 0.04 → "4.0%"
 * @param decimals Decimal places (default 1)
 */
export function formatPercent(rate: number, decimals = 1): string {
  if (!Number.isFinite(rate)) return "—";
  return `${(rate * 100).toFixed(decimals)}%`;
}

/**
 * Format large amounts in compact form: ₹12.5L, ₹1.25Cr
 * Useful for waterfall chart labels where space is tight.
 * @param amount Integer rupees
 */
export function formatCompactINR(amount: number): string {
  if (!Number.isFinite(amount)) return "—";
  amount = Math.abs(amount);

  if (amount >= 1_00_00_000) {
    // Crore (1 Cr = 1,00,00,000)
    return `₹${(amount / 1_00_00_000).toFixed(2).replace(/\.?0+$/, "")}Cr`;
  } else if (amount >= 1_00_000) {
    // Lakh (1 L = 1,00,000)
    return `₹${(amount / 1_00_000).toFixed(2).replace(/\.?0+$/, "")}L`;
  } else if (amount >= 1_000) {
    // Thousand
    return `₹${(amount / 1_000).toFixed(1).replace(/\.?0+$/, "")}K`;
  } else {
    return formatINR(amount);
  }
}
