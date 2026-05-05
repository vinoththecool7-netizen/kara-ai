/**
 * Self-contained tests for uploadDocument in api.ts.
 * Run: cd apps/web && npx tsx src/lib/api.test.ts
 *
 * Uses a manual fetch mock — no test framework required.
 */

import { uploadDocument, HttpError } from "./api";

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
  // Summary
  // -------------------------------------------------------------------------

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) {
    process.exit(1);
  } else {
    console.log("OK");
  }

})();
