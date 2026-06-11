import { describe, expect, it } from "vitest";

import { formatCompactINR, formatINR, formatPercent } from "./format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR(1_500_000)).toBe("₹15,00,000");
    expect(formatINR(97_500)).toBe("₹97,500");
    expect(formatINR(0)).toBe("₹0");
  });

  it("keeps the sign on negative amounts", () => {
    expect(formatINR(-200_000)).toContain("2,00,000");
    expect(formatINR(-200_000)).toContain("-");
  });
});

describe("formatCompactINR", () => {
  it("abbreviates lakhs and crores", () => {
    expect(formatCompactINR(1_250_000)).toContain("L");
    expect(formatCompactINR(25_000_000)).toContain("Cr");
  });
});

describe("formatPercent", () => {
  it("renders a fraction as a percentage", () => {
    expect(formatPercent(0.125)).toContain("12.5");
  });
});
