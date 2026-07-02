import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SetupWizard } from "./SetupWizard";
import { getSetupStatus, saveSetup, testSetup } from "@/lib/api";
import type { SetupStatus } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getSetupStatus: vi.fn(),
  testSetup: vi.fn(),
  saveSetup: vi.fn(),
}));

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

const unconfigured: SetupStatus = {
  configured: false,
  source: null,
  provider: "openai",
  model: "gpt-4o",
  api_key_masked: "",
  ollama: { reachable: false, base_url: "", models: [] },
};

describe("SetupWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getSetupStatus).mockResolvedValue(unconfigured);
  });

  it("renders all provider choices", async () => {
    render(<SetupWizard />);
    expect(await screen.findByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    expect(screen.getByText("Local (Ollama)")).toBeInTheDocument();
  });

  it("shows the env-locked notice instead of the form", async () => {
    vi.mocked(getSetupStatus).mockResolvedValue({
      ...unconfigured,
      configured: true,
      source: "env",
      api_key_masked: "••••9876",
    });
    render(<SetupWizard />);
    expect(
      await screen.findByText(/configured via \.env/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
  });

  it("hides the key field for Ollama and shows detected models", async () => {
    vi.mocked(getSetupStatus).mockResolvedValue({
      ...unconfigured,
      ollama: {
        reachable: true,
        base_url: "http://ollama:11434",
        models: ["llama3.1:latest"],
      },
    });
    render(<SetupWizard />);
    fireEvent.click(await screen.findByText("Local (Ollama)"));
    expect(screen.queryByLabelText(/API key/i)).not.toBeInTheDocument();
    expect(screen.getByText("llama3.1:latest")).toBeInTheDocument();
  });

  it("tests the connection and reports the result", async () => {
    vi.mocked(testSetup).mockResolvedValue({
      ok: true,
      message: "Connection OK.",
    });
    render(<SetupWizard />);
    fireEvent.change(await screen.findByLabelText(/API key/i), {
      target: { value: "sk-test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /test connection/i }));
    expect(await screen.findByText("Connection OK.")).toBeInTheDocument();
    expect(vi.mocked(testSetup)).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "openai", api_key: "sk-test" }),
    );
  });

  it("saves and redirects to chat", async () => {
    vi.mocked(saveSetup).mockResolvedValue({
      ...unconfigured,
      configured: true,
      source: "db",
      api_key_masked: "••••1234",
    });
    render(<SetupWizard />);
    fireEvent.change(await screen.findByLabelText(/API key/i), {
      target: { value: "sk-test-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(vi.mocked(saveSetup)).toHaveBeenCalled());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/chat"));
  });

  it("surfaces a save failure without redirecting", async () => {
    vi.mocked(saveSetup).mockRejectedValue(new Error("Invalid API key."));
    render(<SetupWizard />);
    fireEvent.change(await screen.findByLabelText(/API key/i), {
      target: { value: "sk-bad" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(await screen.findByText(/Invalid API key/)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("pre-fills OpenRouter base URL in the payload", async () => {
    vi.mocked(testSetup).mockResolvedValue({ ok: true, message: "OK" });
    render(<SetupWizard />);
    fireEvent.click(await screen.findByText("OpenRouter"));
    fireEvent.change(screen.getByLabelText(/API key/i), {
      target: { value: "sk-or-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /test connection/i }));
    await waitFor(() =>
      expect(vi.mocked(testSetup)).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: "openai",
          base_url: "https://openrouter.ai/api/v1",
        }),
      ),
    );
  });
});
