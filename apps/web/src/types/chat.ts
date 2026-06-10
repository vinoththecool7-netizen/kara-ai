/**
 * TypeScript interfaces matching the FastAPI backend models.
 * Backend source: apps/api/src/kara_api/routers/chat.py lines 43-73
 */

// ---------------------------------------------------------------------------
// Backend models (mirrors Pydantic models in chat.py)
// ---------------------------------------------------------------------------

export interface ChatRequest {
  message: string;
}

export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
}

export interface MessageResponse {
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls: ToolCallRecord[] | null;
  created_at: string;
  /** Structured card payloads rebuilt server-side from persisted tool results. */
  cards?: {
    tax_breakdown?: TaxBreakdown;
    regime_comparison?: RegimeComparison;
    deduction_gaps?: OptimizationResult;
    capital_gains?: CapitalGainsDetail[];
  } | null;
}

export interface ProfileState {
  slots: Record<string, unknown>;
  ready_intents: string[];
}

export interface SessionResponse {
  session_id: string;
  created_at: string;
  profile_state: ProfileState;
  messages: MessageResponse[];
}

/**
 * Lightweight projection of a session for the sidebar listing.
 *
 * Mirrors `SessionSummary` in apps/api/src/kara_api/routers/chat.py.
 * `title` is derived server-side from the first user message (truncated to
 * 60 characters with an ellipsis, or `"New Chat"` when empty).
 */
export interface SessionSummary {
  id: string;
  created_at: string;
  updated_at: string;
  title: string;
  message_count: number;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  tool_calls_made: {
    tool_name: string;
    arguments: Record<string, unknown>;
    result: string;
    is_error: boolean;
  }[];
  profile_state: ProfileState;
}

export interface DeductionResult {
  section: string;
  claimed: number;
  allowed: number;
  cap: number;
  regime_applicable: boolean;
  note: string;
}

export interface SlabBreakdown {
  lower: number;
  upper: number;     // top slab may use large sentinel (99_99_99_999); handle client-side
  rate: number;      // 0..1 (e.g., 0.04 for 4%)
  taxable_in_slab: number;
  tax_in_slab: number;
}

export interface CapitalGainsDetail {
  asset_class: string;
  gain_type: string;
  section: string;
  purchase_price: number;
  sale_price: number;
  total_gain: number;
  exempt_amount: number;
  taxable_gain: number;
  tax_rate: number;
  tax_amount: number;
  holding_months: number;
  note: string;
}

export interface TaxBreakdown {
  regime: "old" | "new";
  financial_year: string;
  assessment_year: string;
  age_category: "below_60" | "senior" | "super_senior";

  // Income
  gross_salary: number;
  standard_deduction: number;
  net_salary: number;
  house_property_income: number;
  business_income: number;
  capital_gains_income: number;
  other_income: number;
  gross_total_income: number;

  // Deductions
  deductions_applied: DeductionResult[];
  total_deductions: number;
  taxable_income: number;

  // Tax computation
  slab_breakdown: SlabBreakdown[];
  tax_on_normal_income: number;
  tax_on_special_rates: number;
  capital_gains_details: CapitalGainsDetail[];

  // Adjustments
  total_tax_before_surcharge: number;
  surcharge_rate: number;
  surcharge_amount: number;
  marginal_relief_surcharge: number;
  cess_rate: number;
  cess_amount: number;
  rebate_87a: number;
  marginal_relief_87a: number;

  // Final
  total_tax_payable: number;
  effective_tax_rate: number;
  computation_steps: string[];
}

export interface RegimeComparison {
  old_regime: TaxBreakdown;
  new_regime: TaxBreakdown;
  recommended_regime: "old" | "new";
  savings: number;
  breakeven_deductions: number;
  explanation: string;
}

export interface OptimizationSuggestion {
  section: string;
  instrument: string;
  suggested_amount: number;
  potential_tax_saving: number;
  lock_in_years: number | null;
  expected_return_range: number[];
  note: string;
}

export interface OptimizationResult {
  current_tax: number;
  optimized_tax: number;
  total_potential_saving: number;
  suggestions: OptimizationSuggestion[];
  section_80c_used: number;
  section_80c_remaining: number;
  section_80d_used: number;
  section_80d_remaining: number;
  section_80ccd_1b_used: number;
  section_80ccd_1b_remaining: number;
}

// ---------------------------------------------------------------------------
// SSE event discriminated union
// Supports both current (full response) and future (token-by-token) streaming.
// ---------------------------------------------------------------------------

export type SSEEvent =
  | { type: "session_created"; session_id: string }
  | { type: "tool_result"; tool_name: string; result: unknown; is_error: boolean }
  | { type: "content"; text: string }       // current: full response at once
  | { type: "content_delta"; text: string } // future: incremental token stream
  | { type: "advisory"; hint: string }
  | { type: "tax_breakdown"; breakdown: TaxBreakdown }
  | { type: "regime_comparison"; comparison: RegimeComparison }
  | { type: "deduction_gaps"; optimization: OptimizationResult }
  | { type: "capital_gains"; gains: CapitalGainsDetail[] }
  | { type: "done"; session_id: string; profile_state: ProfileState }
  | { type: "error"; message: string }
  | { type: "document_parsed"; summary: ParsedDocumentSummary };

// ---------------------------------------------------------------------------
// Client-side models (adds UI state not present in API responses)
// ---------------------------------------------------------------------------

export interface ToolEvent {
  toolName: string;
  result?: unknown;
  isError: boolean;
}

// ---------------------------------------------------------------------------
// Parsed document summary (result of uploading Form 16 / AIS / 26AS)
// ---------------------------------------------------------------------------

export interface ParsedDocumentSummary {
  document_id: string;
  document_type: "form16" | "ais" | "26as" | string;
  pan: string | null;
  employer_name: string | null;
  period: string | null;
  key_amounts: Record<string, number>;
  fields_filled: number;
  profile_diff?: {
    slots_added: Record<string, unknown>;
    slots_overridden: Record<string, unknown[]>;
    warnings: string[];
  };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  toolEvents?: ToolEvent[];
  taxBreakdown?: TaxBreakdown;
  regimeComparison?: RegimeComparison;
  deductionGaps?: OptimizationResult;
  capitalGains?: CapitalGainsDetail[];
  parsedDocument?: ParsedDocumentSummary;
  /** Proactive advisory tips emitted by the backend after tool calls. */
  advisoryHints?: string[];
  /**
   * Delivery status. Only populated for user messages that failed to send;
   * absent (undefined) means "sent successfully".
   */
  status?: "failed";
}
