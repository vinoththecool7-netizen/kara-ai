import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/types/chat";

const message = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "m1",
  role: "assistant",
  content: "Your tax is **₹97,500**.",
  timestamp: new Date(),
  ...overrides,
});

describe("MessageBubble", () => {
  it("renders markdown content", () => {
    render(<MessageBubble message={message()} />);
    const strong = screen.getByText("₹97,500");
    expect(strong.tagName).toBe("STRONG");
  });

  it("renders advisory hints as tips under the answer", () => {
    render(
      <MessageBubble
        message={message({
          advisoryHints: ["Consider comparing both regimes to save more."],
        })}
      />,
    );
    expect(screen.getByRole("note", { name: "Tax tips" })).toBeInTheDocument();
    expect(
      screen.getByText(/comparing both regimes/i),
    ).toBeInTheDocument();
  });

  it("hides advisory hints while streaming", () => {
    render(
      <MessageBubble
        message={message({ isStreaming: true, advisoryHints: ["Tip!"] })}
      />,
    );
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("offers retry on failed user messages", () => {
    const onRetry = vi.fn();
    render(
      <MessageBubble
        message={message({ role: "user", content: "hello", status: "failed" })}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledWith("m1");
  });
});
