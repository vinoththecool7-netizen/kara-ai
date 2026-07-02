import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePanel } from "./ProfilePanel";
import type { ProfileState } from "@/types/chat";

const profile = (slots: Record<string, unknown>): ProfileState => ({
  slots,
  ready_intents: [],
});

describe("ProfilePanel", () => {
  it("renders nothing when no facts are known", () => {
    const { container } = render(
      <ProfilePanel profileState={profile({})} onClear={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when profileState is null", () => {
    const { container } = render(
      <ProfilePanel profileState={null} onClear={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the number of known details collapsed by default", () => {
    render(
      <ProfilePanel
        profileState={profile({ gross_salary: 1_500_000, regime: "new" })}
        onClear={() => {}}
      />,
    );
    expect(screen.getByText("What Kara knows")).toBeInTheDocument();
    expect(screen.getByText("2 details")).toBeInTheDocument();
    expect(screen.queryByText("Gross Salary")).not.toBeInTheDocument();
  });

  it("expands to show Indian-formatted amounts and section labels", () => {
    render(
      <ProfilePanel
        profileState={profile({ gross_salary: 1_500_000, section_80c: 150_000 })}
        onClear={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /what kara knows/i }));
    expect(screen.getByText("Gross Salary")).toBeInTheDocument();
    expect(screen.getByText("₹15,00,000")).toBeInTheDocument();
    expect(screen.getByText("Section 80C")).toBeInTheDocument();
    expect(screen.getByText("₹1,50,000")).toBeInTheDocument();
  });

  it("calls onClear when the clear control is pressed", () => {
    const onClear = vi.fn();
    render(
      <ProfilePanel profileState={profile({ regime: "old" })} onClear={onClear} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /what kara knows/i }));
    fireEvent.click(screen.getByText(/clear these details/i));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
