/**
 * Typed fetch client for Exchange endpoints.
 */

const API_BASE =
  typeof window === "undefined"
    ? process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8001"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string;
};

async function apiFetch<T>(
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, token } = opts;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    const error = new ApiError(
      err.error || err.detail?.error || `API error ${res.status}`,
      res.status,
      err.detail
    );
    throw error;
  }

  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  detail: Record<string, unknown> | null;

  constructor(
    message: string,
    status: number,
    detail: Record<string, unknown> | null = null
  ) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// -- Interfaces --

export interface VerifyResponse {
  result_id: string;
  source_url: string | null;
  publication: string | null;
  verified_claim_count: number;
  verdict: string;
  usage: UsageCheck;
  result: PipelineResult;
}

export interface UsageCheck {
  allowed: boolean;
  used: number;
  limit: number;
}

export interface PipelineResult {
  request_id: string;
  timestamp: string;
  input_text: string;
  annotated_text: string;
  sentences: SentenceResult[];
  coverage: Coverage;
  decision: string;
  decision_reasons: Array<{ claim: string; reason: string }>;
  config: Record<string, unknown>;
  audit: { sources_consulted: number; processing_time_ms: number; trace_id: string };
}

export interface SentenceResult {
  text: string;
  decision: string;
  claims: ClaimResult[];
}

export interface ClaimResult {
  text: string;
  position: { start: number; end: number };
  status: "corroborated" | "contradicted" | "unsupported" | "out_of_scope";
  confirmation_strength: "strong" | "moderate" | "weak" | null;
  fix: ContradictedFix | UnsupportedFix | OutOfScopeFix | null;
  sources: ClaimSource[];
}

export interface ClaimSource {
  id: string;
  name: string;
  source_type: string;
  connector_id: string | null;
  url: string | null;
  authority_level: string;
  freshness: string;
  detail: {
    ai_asserted: string;
    source_states: string;
    discrepancy_type: string | null;
    summary: string;
  };
}

export interface ContradictedFix {
  suggested_text: string;
  confidence: "high" | "medium" | "low";
  basis: string;
}

export interface UnsupportedFix {
  suggested_text: null;
  action: "remove_or_qualify";
  suggestion: string;
}

export interface OutOfScopeFix {
  suggested_text: null;
  action: "flag_for_human_review";
  suggestion: string;
}

export interface Coverage {
  total_sentences: number;
  total_claims: number;
  corroborated: number;
  contradicted: number;
  unsupported: number;
  out_of_scope: number;
  coverage_ratio: number;
}

export interface ExchangeResult {
  result_id: string;
  source_url: string | null;
  publication: string | null;
  created_at: string | null;
  verified_claim_count: number;
  verdict: string;
  result: PipelineResult;
  input_text?: string;
  user_id?: string;
}

export interface ExchangeResultSummary {
  result_id: string;
  source_url: string | null;
  publication: string | null;
  created_at: string | null;
  verified_claim_count: number;
  verdict: string;
  input_text: string;
}

export interface PaginatedResults {
  results: ExchangeResultSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface UsageResponse {
  month: string;
  used: number;
  limit: number;
  remaining: number;
  plan: string;
}

// -- SSE stream types --

export interface PreviewClaim {
  text: string;
  status: "checking";
}

export interface VerifiedClaim {
  text: string;
  status: "corroborated" | "contradicted" | "unsupported" | "out_of_scope";
  position: { start: number; end: number };
  confirmation_strength: "strong" | "moderate" | "weak" | null;
  fix: ContradictedFix | UnsupportedFix | OutOfScopeFix | null;
  sources: ClaimSource[];
}

export type StreamEvent =
  | { type: "status"; phase: string; url?: string; publication?: string; source_url?: string; claim_count?: number }
  | { type: "claims_extracted"; claims: PreviewClaim[]; count: number }
  | { type: "claim_verified"; claim: VerifiedClaim }
  | { type: "result"; data: VerifyResponse }
  | { type: "error"; error: string; fallback?: boolean; used?: number; limit?: number };

export interface StreamCallbacks {
  onStatus?: (phase: string, detail: Record<string, unknown>) => void;
  onClaimsExtracted?: (claims: PreviewClaim[]) => void;
  onClaimVerified?: (claim: VerifiedClaim) => void;
  onResult?: (result: VerifyResponse) => void;
  onError?: (error: string, detail: Record<string, unknown>) => void;
}

/**
 * Streaming verify via SSE. Calls callbacks as events arrive.
 * Falls back to the non-streaming endpoint if SSE fails to connect.
 */
export async function verifyStream(
  input: string,
  callbacks: StreamCallbacks,
  token?: string,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const apiBase =
    typeof window === "undefined"
      ? process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
      : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

  const res = await fetch(`${apiBase}/api/public/verify/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({ input }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { error: res.statusText } }));
    const msg = err.detail?.error || err.error || `API error ${res.status}`;
    callbacks.onError?.(msg, err.detail || {});
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    // Fallback to non-streaming
    const result = await verify(input, token);
    callbacks.onResult?.(result);
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      let eventType = "message";
      let eventData = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          eventData += line.slice(6);
        }
      }

      if (!eventData) continue;

      try {
        const parsed = JSON.parse(eventData);

        switch (eventType) {
          case "status":
            callbacks.onStatus?.(parsed.phase, parsed);
            break;
          case "claims_extracted":
            callbacks.onClaimsExtracted?.(parsed.claims);
            break;
          case "claim_verified":
            callbacks.onClaimVerified?.(parsed);
            break;
          case "result":
            callbacks.onResult?.(parsed);
            break;
          case "error":
            callbacks.onError?.(parsed.error, parsed);
            break;
        }
      } catch {
        // skip malformed events
      }
    }
  }
}

// -- API functions --

export async function verify(input: string, token?: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>("/api/public/verify", {
    method: "POST",
    body: { input },
    token,
  });
}

export async function getResult(id: string): Promise<ExchangeResult> {
  return apiFetch<ExchangeResult>(`/api/results/${id}`);
}

export async function getResults(
  token: string,
  params?: { verdict?: string; date_from?: string; limit?: number; offset?: number }
): Promise<PaginatedResults> {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : "";
  return apiFetch<PaginatedResults>(`/api/results${qs}`, { token });
}

export async function getUsage(token: string): Promise<UsageResponse> {
  return apiFetch<UsageResponse>("/api/usage", { token });
}

export async function claimResult(
  token: string,
  resultId: string
): Promise<ExchangeResult> {
  return apiFetch<ExchangeResult>("/api/results", {
    method: "POST",
    body: { result_id: resultId },
    token,
  });
}
