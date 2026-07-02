/**
 * Self-contained tests for uploadDocument in api.ts.
 * Run: cd apps/web && npx tsx src/lib/api.test.ts
 *
 * Uses a manual fetch mock — no test framework required.
 */

import {
  uploadDocument,
  getSetupStatus,
  saveSetup,
  testSetup,
  HttpError,
  type SetupStatus,
} from "./api";

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
    console.error(
      `  FAIL: ${msg} — expected ${String(expected)}, got ${String(actual)}`,
    );
  }
}

async function assertRejects(
  fn: () => Promise<unknown>,
  check: (err: unknown) => boolean,
  msg: string,
): Promise<void> {
  try {
    await fn();
    failed++;
    console.error(`  FAIL: ${msg} — expected rejection but resolved`);
  } catch (err) {
    if (check(err)) {
      passed++;
    } else {
      failed++;
      console.error(
        `  FAIL: ${msg} — rejection check failed, got: ${String(err)}`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Mock fetch helpers
// ---------------------------------------------------------------------------

type FetchMock = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

const originalFetch = globalThis.fetch;
const g = globalThis as Record<string, unknown>;

function mockFetch(impl: FetchMock): void {
  g["fetch"] = impl;
}

function restoreFetch(): void {
  g["fetch"] = originalFetch;
}

function makeResponse(body: unknown, status = 200): Response {
  const json = JSON.stringify(body);
  return new Response(json, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Run all tests inside an async IIFE (required for cjs tsx compatibility)
// ---------------------------------------------------------------------------

void (async () => {

  // -------------------------------------------------------------------------
  // Test: client-side size guard throws HttpError(413) before fetch is called
  // -------------------------------------------------------------------------

  {
    let fetchCalled = false;
    mockFetch(async () => {
      fetchCalled = true;
      return makeResponse({}, 200);
    });

    const bigFile = new File([new Uint8Array(11 * 1024 * 1024)], "big.pdf", {
      type: "application/pdf",
    });

    await assertRejects(
      () => uploadDocument("session-123", bigFile, "auto"),
      (err) =>
        err instanceof HttpError &&
        err.status === 413 &&
        err.message.includes("10 MB"),
      "client-side size guard throws HttpError(413) for file > 10 MB",
    );
    assert(!fetchCalled, "fetch is NOT called when client-side guard fires");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: uploadDocument builds correct FormData fields
  // -------------------------------------------------------------------------

  {
    let capturedBody: unknown = null;
    let capturedUrl: string | null = null;
    let capturedMethod: string | null = null;

    const mockResult = {
      document_id: "doc-abc",
      document_type: "form16",
      parsed_summary: {
        document_id: "doc-abc",
        document_type: "form16",
        pan: "ABCDE1234F",
        employer_name: "Acme Corp",
        period: "2024-25",
        key_amounts: { gross_salary: 1200000, total_tds: 120000 },
        fields_filled: 8,
      },
      profile_diff: {
        slots_added: { gross_salary: 1200000 },
        slots_overridden: {},
        warnings: [],
      },
      warnings: [],
    };

    mockFetch(async (input, init) => {
      capturedUrl = String(input);
      capturedMethod = init?.method ?? null;
      capturedBody = init?.body;
      return makeResponse(mockResult, 200);
    });

    const smallFile = new File(["PDF content here"], "form16.pdf", {
      type: "application/pdf",
    });

    const result = await uploadDocument("sess-xyz", smallFile, "form16");

    assertEqual(capturedUrl, "/api/v1/documents/upload", "uploads to correct endpoint");
    assertEqual(capturedMethod, "POST", "uses POST method");
    assert(capturedBody instanceof FormData, "body is FormData");
    if (capturedBody instanceof FormData) {
      assertEqual(capturedBody.get("session_id"), "sess-xyz", "FormData has session_id");
      assertEqual(capturedBody.get("document_type"), "form16", "FormData has document_type");
      const fileField = capturedBody.get("file");
      assert(fileField instanceof File, "FormData has file field");
      if (fileField instanceof File) {
        assertEqual(fileField.name, "form16.pdf", "FormData file has correct name");
      }
    }
    assertEqual(result.document_id, "doc-abc", "returns document_id from response");
    assertEqual(result.parsed_summary.pan, "ABCDE1234F", "returns parsed pan");
    assertEqual(result.parsed_summary.employer_name, "Acme Corp", "returns employer_name");

    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: non-2xx response throws HttpError with status code
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({ detail: "Unsupported file format" }, 422),
    );

    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    await assertRejects(
      () => uploadDocument("sess-err", file, "auto"),
      (err) =>
        err instanceof HttpError &&
        err.status === 422 &&
        err.message.includes("422"),
      "non-2xx throws HttpError with correct status",
    );

    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: defaults document_type to "auto"
  // -------------------------------------------------------------------------

  {
    let capturedDocType: string | null = null;

    mockFetch(async (_, init) => {
      capturedDocType = (init?.body as FormData)?.get("document_type") as string;
      return makeResponse({
        document_id: "doc-default",
        document_type: "auto",
        parsed_summary: {
          document_id: "doc-default",
          document_type: "auto",
          pan: null,
          employer_name: null,
          period: null,
          key_amounts: {},
          fields_filled: 0,
        },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: [] },
        warnings: [],
      }, 200);
    });

    const file = new File(["data"], "mystery.pdf", { type: "application/pdf" });
    await uploadDocument("sess-default", file); // no documentType arg

    assertEqual(capturedDocType, "auto", "defaults document_type to 'auto'");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: file exactly at 10 MB limit is accepted (not rejected client-side)
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({
        document_id: "doc-edge",
        document_type: "auto",
        parsed_summary: {
          document_id: "doc-edge",
          document_type: "auto",
          pan: null,
          employer_name: null,
          period: null,
          key_amounts: {},
          fields_filled: 0,
        },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: [] },
        warnings: [],
      }, 200),
    );

    const exactLimitFile = new File(
      [new Uint8Array(10 * 1024 * 1024)],
      "exact.pdf",
      { type: "application/pdf" },
    );

    let didThrow = false;
    try {
      await uploadDocument("sess-edge", exactLimitFile, "auto");
    } catch {
      didThrow = true;
    }
    assert(!didThrow, "file exactly at 10 MB is accepted (no client-side rejection)");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: client-side 413 message matches spec exactly
  // -------------------------------------------------------------------------

  {
    const bigFile = new File([new Uint8Array(11 * 1024 * 1024)], "big.pdf", {
      type: "application/pdf",
    });

    let errorMessage: string | null = null;
    try {
      await uploadDocument("s", bigFile, "auto");
    } catch (err) {
      if (err instanceof HttpError) errorMessage = err.message;
    }
    assertEqual(
      errorMessage,
      "File too large. Maximum is 10 MB.",
      "client-side 413 message matches spec exactly",
    );
  }

  // -------------------------------------------------------------------------
  // Test: server 415 response throws HttpError(415)
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({ detail: "Unsupported media type" }, 415),
    );

    const file = new File(["content"], "test.docx");

    await assertRejects(
      () => uploadDocument("s", file, "auto"),
      (err) => err instanceof HttpError && (err as HttpError).status === 415,
      "server 415 throws HttpError(415)",
    );
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: server 413 response throws HttpError(413) (distinct from client-side)
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({ detail: "File too large" }, 413),
    );

    // Under 10 MB so client-side guard doesn't fire
    const file = new File(["content"], "medium.pdf", { type: "application/pdf" });

    await assertRejects(
      () => uploadDocument("s", file, "auto"),
      (err) => err instanceof HttpError && (err as HttpError).status === 413,
      "server 413 throws HttpError(413)",
    );
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: network error (fetch throws) propagates
  // -------------------------------------------------------------------------

  {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    const file = new File(["data"], "f.pdf", { type: "application/pdf" });

    await assertRejects(
      () => uploadDocument("sess-net", file, "auto"),
      (err) => err instanceof TypeError && (err as TypeError).message === "Failed to fetch",
      "network error propagates to caller",
    );
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: response with warnings array is returned correctly
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({
        document_id: "doc-warn",
        document_type: "form16",
        parsed_summary: {
          document_id: "doc-warn",
          document_type: "form16",
          pan: "ABCDE1234F",
          employer_name: "Corp",
          period: "2024-25",
          key_amounts: {},
          fields_filled: 3,
        },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: ["TDS mismatch"] },
        warnings: ["TDS mismatch", "Missing Part B"],
      }, 200),
    );

    const file = new File(["pdf"], "form16.pdf", { type: "application/pdf" });
    const result = await uploadDocument("sess-warn", file, "form16");

    assertEqual(result.warnings.length, 2, "returns warnings array with correct length");
    assertEqual(result.profile_diff.warnings[0], "TDS mismatch", "profile_diff.warnings preserved");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: AIS document type is sent in FormData
  // -------------------------------------------------------------------------

  {
    let capturedDocType: string | null = null;
    mockFetch(async (_, init) => {
      capturedDocType = (init?.body as FormData)?.get("document_type") as string;
      return makeResponse({
        document_id: "ais-1", document_type: "ais",
        parsed_summary: { document_id: "ais-1", document_type: "ais", pan: null, employer_name: null, period: null, key_amounts: {}, fields_filled: 0 },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: [] }, warnings: [],
      }, 200);
    });

    const file = new File(["{}"], "ais.json", { type: "application/json" });
    await uploadDocument("s", file, "ais");
    assertEqual(capturedDocType, "ais", "AIS document type is sent in FormData");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: 26as document type is sent in FormData
  // -------------------------------------------------------------------------

  {
    let capturedDocType: string | null = null;
    mockFetch(async (_, init) => {
      capturedDocType = (init?.body as FormData)?.get("document_type") as string;
      return makeResponse({
        document_id: "26as-1", document_type: "26as",
        parsed_summary: { document_id: "26as-1", document_type: "26as", pan: null, employer_name: null, period: null, key_amounts: {}, fields_filled: 0 },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: [] }, warnings: [],
      }, 200);
    });

    const file = new File(["%PDF"], "26as.pdf", { type: "application/pdf" });
    await uploadDocument("s", file, "26as");
    assertEqual(capturedDocType, "26as", "26as document type is sent in FormData");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: file just over 10 MB (10MB + 1 byte) is rejected client-side
  // -------------------------------------------------------------------------

  {
    const oneByteTooLarge = new File(
      [new Uint8Array(10 * 1024 * 1024 + 1)],
      "over.pdf",
      { type: "application/pdf" },
    );

    await assertRejects(
      () => uploadDocument("s", oneByteTooLarge, "auto"),
      (err) => err instanceof HttpError && (err as HttpError).status === 413,
      "file 1 byte over 10 MB is rejected with HttpError(413)",
    );
  }

  // -------------------------------------------------------------------------
  // Test: onProgress parameter can be passed without TypeScript error
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({
        document_id: "prog-1", document_type: "form16",
        parsed_summary: { document_id: "prog-1", document_type: "form16", pan: null, employer_name: null, period: null, key_amounts: {}, fields_filled: 0 },
        profile_diff: { slots_added: {}, slots_overridden: {}, warnings: [] }, warnings: [],
      }, 200),
    );

    const file = new File(["data"], "f.pdf", { type: "application/pdf" });
    let progressCalled = false;
    // onProgress is currently a no-op stub; just verify it can be passed without crashing
    const result = await uploadDocument("s", file, "auto", () => { progressCalled = true; });
    assert(result.document_id === "prog-1", "uploadDocument accepts onProgress callback");
    assert(!progressCalled, "onProgress is not yet called (stub)");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: parsed_summary.fields_filled is returned correctly
  // -------------------------------------------------------------------------

  {
    mockFetch(async () =>
      makeResponse({
        document_id: "fields-1", document_type: "form16",
        parsed_summary: { document_id: "fields-1", document_type: "form16", pan: "XYZAB1234C", employer_name: "MegaCorp", period: "2024-25", key_amounts: { gross_salary: 800000 }, fields_filled: 12 },
        profile_diff: { slots_added: { gross_salary: 800000 }, slots_overridden: {}, warnings: [] }, warnings: [],
      }, 200),
    );

    const file = new File(["pdf"], "f.pdf", { type: "application/pdf" });
    const result = await uploadDocument("s", file, "form16");
    assertEqual(result.parsed_summary.fields_filled, 12, "fields_filled returned correctly");
    assertEqual(result.parsed_summary.pan, "XYZAB1234C", "PAN returned correctly");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: getSetupStatus parses the status payload
  // -------------------------------------------------------------------------

  {
    const status: SetupStatus = {
      configured: false,
      source: null,
      provider: "openai",
      model: "gpt-4o",
      api_key_masked: "",
      ollama: { reachable: false, base_url: "", models: [] },
    };
    let capturedUrl: string | null = null;
    mockFetch(async (input) => {
      capturedUrl = String(input);
      return makeResponse(status, 200);
    });

    const result = await getSetupStatus();
    assertEqual(capturedUrl, "/api/v1/setup/status", "getSetupStatus hits /api/v1/setup/status");
    assertEqual(result.configured, false, "getSetupStatus returns configured flag");
    assertEqual(result.ollama.reachable, false, "getSetupStatus returns ollama status");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: saveSetup POSTs the payload and returns status
  // -------------------------------------------------------------------------

  {
    const status: SetupStatus = {
      configured: true,
      source: "db",
      provider: "openai",
      model: "gpt-4o",
      api_key_masked: "••••1234",
      ollama: { reachable: false, base_url: "", models: [] },
    };
    let capturedMethod: string | null = null;
    let capturedBody: string | null = null;
    mockFetch(async (_input, init) => {
      capturedMethod = init?.method ?? null;
      capturedBody = String(init?.body);
      return makeResponse(status, 200);
    });

    const result = await saveSetup({
      provider: "openai",
      api_key: "sk-x",
      model: "",
      base_url: "",
      ollama_base_url: "",
    });
    assertEqual(capturedMethod, "POST", "saveSetup uses POST");
    assert(
      String(capturedBody).includes('"provider":"openai"'),
      "saveSetup sends the provider in the body",
    );
    assertEqual(result.configured, true, "saveSetup returns the new status");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Test: saveSetup surfaces HTTP errors; testSetup returns the result
  // -------------------------------------------------------------------------

  {
    mockFetch(async () => makeResponse({ detail: "Invalid API key." }, 400));
    await assertRejects(
      () =>
        saveSetup({
          provider: "openai",
          api_key: "bad",
          model: "",
          base_url: "",
          ollama_base_url: "",
        }),
      (err) =>
        err instanceof HttpError &&
        err.status === 400 &&
        err.message.includes("Invalid API key."),
      "saveSetup throws HttpError with the server detail",
    );
    restoreFetch();

    mockFetch(async () => makeResponse({ ok: true, message: "Connection OK." }, 200));
    const test = await testSetup({
      provider: "openai",
      api_key: "sk-x",
      model: "",
      base_url: "",
      ollama_base_url: "",
    });
    assertEqual(test.ok, true, "testSetup returns ok flag");
    assertEqual(test.message, "Connection OK.", "testSetup returns message");
    restoreFetch();
  }

  // -------------------------------------------------------------------------
  // Summary
  // -------------------------------------------------------------------------

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) {
    process.exit(1);
  } else {
    console.log("OK");
  }

})();
