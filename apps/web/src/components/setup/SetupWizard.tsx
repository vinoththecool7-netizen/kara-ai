"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  getSetupStatus,
  saveSetup,
  testSetup,
  type SetupPayload,
  type SetupStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ProviderChoice = "openai" | "anthropic" | "openrouter" | "ollama";

const PROVIDER_LABELS: Record<ProviderChoice, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  openrouter: "OpenRouter",
  ollama: "Local (Ollama)",
};

const PROVIDER_HINTS: Record<ProviderChoice, string> = {
  openai: "GPT models — platform.openai.com",
  anthropic: "Claude models — console.anthropic.com",
  openrouter: "One key, many models — openrouter.ai",
  ollama: "Runs on your machine — no key, fully private",
};

const DEFAULT_MODELS: Record<ProviderChoice, string> = {
  openai: "gpt-4o",
  anthropic: "claude-sonnet-4-20250514",
  openrouter: "openai/gpt-4o",
  ollama: "llama3.1",
};

function toPayload(
  choice: ProviderChoice,
  apiKey: string,
  model: string,
  ollamaBaseUrl: string,
): SetupPayload {
  return {
    provider: choice === "openrouter" ? "openai" : choice,
    api_key: choice === "ollama" ? "" : apiKey,
    model: model || DEFAULT_MODELS[choice],
    base_url: choice === "openrouter" ? "https://openrouter.ai/api/v1" : "",
    ollama_base_url: choice === "ollama" ? ollamaBaseUrl : "",
  };
}

/**
 * First-run configuration form. Shown when the backend reports it has no
 * LLM configured; also reachable later at /setup to switch providers
 * (unless config is locked in .env on the server).
 */
export function SetupWizard() {
  const router = useRouter();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [choice, setChoice] = useState<ProviderChoice>("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [feedback, setFeedback] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [busy, setBusy] = useState<"test" | "save" | null>(null);

  useEffect(() => {
    getSetupStatus()
      .then((s) => {
        setStatus(s);
        if (!s.configured && s.ollama.reachable) setChoice("ollama");
      })
      .catch(() => setStatus(null));
  }, []);

  const envLocked = status?.source === "env";
  const ollama = status?.ollama;

  const run = async (kind: "test" | "save") => {
    setBusy(kind);
    setFeedback(null);
    const payload = toPayload(choice, apiKey, model, ollama?.base_url ?? "");
    try {
      if (kind === "test") {
        setFeedback(await testSetup(payload));
      } else {
        await saveSetup(payload);
        router.replace("/chat");
      }
    } catch (err) {
      setFeedback({
        ok: false,
        message: err instanceof Error ? err.message : "Request failed",
      });
    } finally {
      setBusy(null);
    }
  };

  if (envLocked) {
    return (
      <div className="mx-auto max-w-xl p-8 text-center">
        <h1 className="text-2xl font-semibold">
          Kara is configured via .env
        </h1>
        <p className="mt-2 text-muted-foreground">
          This server manages its LLM settings in <code>apps/api/.env</code>.
          Edit that file and restart to change providers.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Set up Kara</h1>
      <p className="mt-1 text-muted-foreground">
        Pick who runs the language model. Rupee math always runs locally in
        the deterministic tax engine — the LLM only converses.
      </p>

      <fieldset className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <legend className="sr-only">LLM provider</legend>
        {(Object.keys(PROVIDER_LABELS) as ProviderChoice[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => {
              setChoice(p);
              setModel("");
              setFeedback(null);
            }}
            aria-pressed={choice === p}
            className={cn(
              "rounded-lg border p-3 text-left transition-colors",
              choice === p
                ? "border-blue-600 ring-1 ring-blue-600"
                : "border-border hover:border-blue-300",
            )}
          >
            <span className="font-medium">{PROVIDER_LABELS[p]}</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {p === "ollama" && ollama?.reachable
                ? "detected on this machine ✓"
                : PROVIDER_HINTS[p]}
            </span>
          </button>
        ))}
      </fieldset>

      {choice !== "ollama" ? (
        <label className="mt-6 block">
          <span className="text-sm font-medium">API key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={choice === "anthropic" ? "sk-ant-…" : "sk-…"}
            autoComplete="off"
            className="mt-1 w-full rounded-md border border-border bg-background p-2"
          />
          <span className="mt-1 block text-xs text-muted-foreground">
            Stored only on your server; never shown again in full.
          </span>
        </label>
      ) : (
        <div className="mt-6">
          <span className="text-sm font-medium">Detected models</span>
          {ollama?.reachable && ollama.models.length > 0 ? (
            <ul className="mt-1 flex flex-wrap gap-2">
              {ollama.models.map((m) => (
                <li key={m}>
                  <button
                    type="button"
                    onClick={() => setModel(m)}
                    aria-pressed={model === m}
                    className={cn(
                      "rounded-full border px-3 py-1 text-sm",
                      model === m
                        ? "border-blue-600 bg-blue-50 font-medium"
                        : "border-border",
                    )}
                  >
                    {m}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              No local Ollama found. Start it with{" "}
              <code>docker compose --profile local up -d</code> and reload
              this page.
            </p>
          )}
        </div>
      )}

      <label className="mt-4 block">
        <span className="text-sm font-medium">Model</span>
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={DEFAULT_MODELS[choice]}
          className="mt-1 w-full rounded-md border border-border bg-background p-2"
        />
        <span className="mt-1 block text-xs text-muted-foreground">
          Leave empty for the default ({DEFAULT_MODELS[choice]}).
        </span>
      </label>

      {feedback && (
        <p
          role="status"
          className={cn(
            "mt-4 text-sm",
            feedback.ok ? "text-emerald-700" : "text-red-600",
          )}
        >
          {feedback.message}
        </p>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void run("test")}
          disabled={busy !== null}
          className="rounded-md border border-border px-4 py-2 disabled:opacity-50"
        >
          {busy === "test" ? "Testing…" : "Test connection"}
        </button>
        <button
          type="button"
          onClick={() => void run("save")}
          disabled={busy !== null}
          className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {busy === "save" ? "Saving…" : "Save & start chatting"}
        </button>
      </div>
    </div>
  );
}
