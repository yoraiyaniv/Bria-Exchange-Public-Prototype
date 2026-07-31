/**
 * Typed fetch client — wraps all backend API calls.
 * Automatically attaches the user's JWT token from NextAuth session.
 */

// Server-side (Server Components, API routes): use API_URL so Docker container
// can reach the backend by service name (http://dashboard-api:8001).
// Browser-side: use NEXT_PUBLIC_API_URL (http://localhost:8001).
const API_BASE =
  typeof window === "undefined"
    ? process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string;
};

async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
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
    throw new Error(err.error || `API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// Auth
export const authApi = {
  signup: (data: { name: string; email: string; password: string; orgName: string }) =>
    apiFetch("/auth/signup", { method: "POST", body: data }),
  login: (data: { email: string; password: string }) =>
    apiFetch("/auth/login", { method: "POST", body: data }),
};

// Dashboard
export const dashboardApi = {
  get: (token: string, period = "30d") =>
    apiFetch<DashboardData>(`/api/dashboard?period=${period}`, { token }),
};

// Cost estimation
export const costApi = {
  get: (token: string, period = "30d") =>
    apiFetch<CostData>(`/api/cost?period=${period}`, { token }),
};

// Verifications
export const verifyApi = {
  run: (token: string, data: { text: string; config: unknown; agentId?: string; parentVerificationId?: string }) =>
    apiFetch<VerificationResponse>("/api/verify", { method: "POST", body: data, token }),
  get: (token: string, id: string) =>
    apiFetch(`/api/verify/${id}`, { token }),
  claim: (token: string, id: string) =>
    apiFetch(`/api/verify/${id}/claim`, { method: "PATCH", token }),
  submitReview: (token: string, id: string, data: { reviewActions?: unknown; correctedText?: string; outcome: "approved" | "rejected"; reviewNote?: string }) =>
    apiFetch(`/api/verify/${id}/review`, { method: "PATCH", body: data, token }),
};

// Review queue
export const reviewApi = {
  list: (token: string, tab?: string) => {
    const qs = tab ? `?tab=${tab}` : "";
    return apiFetch<Verification[]>(`/api/review${qs}`, { token });
  },
};

// Audit
export const auditApi = {
  list: (token: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return apiFetch<{ verifications: Verification[]; total: number; page: number; limit: number }>(`/api/audit${qs}`, { token });
  },
  exportUrl: (token: string, params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return `${API_BASE}/api/audit/export${qs}`;
  },
};

// Agents
export const agentsApi = {
  list: (token: string) => apiFetch<Agent[]>("/api/agents", { token }),
  create: (token: string, data: Partial<Agent>) => apiFetch<Agent>("/api/agents", { method: "POST", body: data, token }),
  update: (token: string, id: string, data: Partial<Agent>) => apiFetch<Agent>(`/api/agents/${id}`, { method: "PUT", body: data, token }),
  delete: (token: string, id: string) => apiFetch(`/api/agents/${id}`, { method: "DELETE", token }),
  regenerateKey: (token: string, id: string) => apiFetch<{ apiKey: string }>(`/api/agents/${id}/regenerate-key`, { method: "POST", token }),
};

// Sources
export const sourcesApi = {
  getCatalog: (token: string) =>
    apiFetch<{ sources: Connector[]; comingSoon: ComingSoonSource[] }>("/api/sources/catalog", { token }),
  getConnected: (token: string) => apiFetch<ConnectedSource[]>("/api/sources", { token }),
  connect: (token: string, data: { connectorId: string; name?: string; domain?: string; apiKey?: string }) =>
    apiFetch<ConnectedSource>("/api/sources", { method: "POST", body: data, token }),
  disconnect: (token: string, id: string) => apiFetch(`/api/sources/${id}`, { method: "DELETE", token }),
  testConnection: (token: string, id: string) => apiFetch<{ ok: boolean; latencyMs: number; message?: string }>(`/api/sources/${id}/test`, { method: "POST", token }),
  // Aliases for backwards compat
  catalog: (token: string) =>
    apiFetch<{ sources: Connector[]; comingSoon: ComingSoonSource[] }>("/api/sources/catalog", { token }),
  list: (token: string) => apiFetch<ConnectedSource[]>("/api/sources", { token }),
  test: (token: string, id: string) => apiFetch<{ ok: boolean; latencyMs: number; message?: string }>(`/api/sources/${id}/test`, { method: "POST", token }),

  // Coming Soon — demand signals
  toggleInterest: (token: string, connectorId: string, notifyOnLaunch: boolean) =>
    apiFetch<{ voted: boolean; notifyOnLaunch: boolean; interestCount: number }>(
      `/api/sources/interest/${connectorId}`,
      { method: "POST", body: { notifyOnLaunch }, token },
    ),
  updateNotify: (token: string, connectorId: string, notifyOnLaunch: boolean) =>
    apiFetch<{ notifyOnLaunch: boolean }>(
      `/api/sources/interest/${connectorId}/notify`,
      { method: "PATCH", body: { notifyOnLaunch }, token },
    ),

  // Custom sources
  getCustomSources: (token: string) =>
    apiFetch<{ mine: CustomSource[]; community: CustomSource[] }>("/api/sources/custom", { token }),
  getCustomSource: (token: string, id: string) =>
    apiFetch<CustomSource>(`/api/sources/custom/${id}`, { token }),
  createCustomSource: (token: string, body: object) =>
    apiFetch<CustomSource>("/api/sources/custom", { method: "POST", body, token }),
  uploadCustomSource: async (token: string, formData: FormData): Promise<CustomSource> => {
    const res = await fetch(`${API_BASE}/api/sources/custom/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  updateCustomSource: (token: string, id: string, body: object) =>
    apiFetch<CustomSource>(`/api/sources/custom/${id}`, { method: "PATCH", body, token }),
  deleteCustomSource: (token: string, id: string) =>
    apiFetch(`/api/sources/custom/${id}`, { method: "DELETE", token }),
  testCustomSource: (token: string, id: string) =>
    apiFetch<{ status: string; message?: string }>(`/api/sources/custom/${id}/test`, { method: "POST", token }),
};

// Settings
export const settingsApi = {
  get: (token: string) => apiFetch<OrgSettings>("/api/settings", { token }),
  update: (token: string, data: Partial<OrgSettings["org"]>) => apiFetch("/api/settings", { method: "PUT", body: data, token }),
  regenerateKey: (token: string) => apiFetch<{ apiKey: string }>("/api/settings/regenerate-key", { method: "POST", token }),
  invite: (token: string, data: { email: string; name: string; role?: string }) =>
    apiFetch("/api/settings/invite", { method: "POST", body: data, token }),
  updateRole: (token: string, userId: string, role: string) =>
    apiFetch(`/api/settings/members/${userId}/role`, { method: "PUT", body: { role }, token }),
};

// ---- Types ----

export interface Verification {
  id: string;
  inputText: string;
  domain: string;
  decision: "pass" | "flag" | "block";
  decisionReasons: Array<{ claim: string; reason: string }>;
  totalClaims: number;
  corroboratedCount: number;
  contradictedCount: number;
  unsupportedCount: number;
  outOfScopeCount: number;
  coverageRatio: number;
  corroborationRate: number;
  fullResponse: VerificationResponse;
  config: PolicyConfig;
  reviewStatus: string;
  reviewedBy: string | null;
  reviewedAt: string | null;
  reviewNote: string | null;
  reviewActions: ReviewAction[] | null;
  correctedText: string | null;
  parentVerificationId: string | null;
  latencyMs: number;
  traceId: string;
  agentId: string | null;
  agent?: string | null;
  createdAt: string;
  iterationCount?: number;
}

export interface VerificationResponse {
  request_id: string;
  timestamp: string;
  input_text: string;
  annotated_text: string;
  sentences: SentenceResult[];
  coverage: Coverage;
  decision: "pass" | "flag" | "block";
  decision_reasons: Array<{ claim: string; reason: string }>;
  config: PolicyConfig;
  audit: { sources_consulted: number; processing_time_ms: number; trace_id: string };
}

export interface SentenceResult {
  text: string;
  decision: "pass" | "flag" | "block" | "out_of_scope";
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
  source_type: "live_api" | "bria_corpus";
  connector_id: string | null;
  url: string | null;
  authority_level: "primary" | "institutional" | "secondary" | "tertiary";
  freshness: "current" | "aging" | "stale" | "deprecated";
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

export interface PolicyConfig {
  unsupported_policy: "accept" | "flag" | "block";
  out_of_scope_policy: "accept" | "flag" | "block";
  contradiction_policy: "flag" | "block";
  flag_extrapolations: boolean;
  require_acknowledgement_note: boolean;
  domain: string;
  policy_profile: "strict" | "moderate" | "permissive";
  connectedSourceIds?: string[];
}

export interface ReviewAction {
  claimText: string;
  action: "applied_fix" | "acknowledged" | "escalated" | "removed" | "qualified";
  note?: string | null;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
}

export interface Agent {
  id: string;
  name: string;
  type: string;
  owner: string;
  policy: PolicyConfig;
  notificationOverride?: unknown;
  createdAt: string;
  apiKey?: string | null;         // masked preview normally; full key only on create/regenerate
}

export interface Connector {
  id: string;
  name: string;
  description: string;
  domain: string;
  authorityLevel: string;
  isFree: boolean;
  requiresKey: boolean;
  notes: string;
}

export interface ConnectedSource {
  id: string;
  connectorId: string;
  name: string;
  domain: string;
  authorityLevel: string;
  apiKey: string | null;
  status: string;
  lastTestedAt: string | null;
  createdAt: string;
}

export interface ComingSoonSource {
  id: string;
  name: string;
  domain: string;
  authorityLevel: string;
  category: string;
  description: string;
  examples: string[];
  partner: string;
  interestCount: number;
  orgHasVoted: boolean;
  orgNotifyOnLaunch: boolean;
}

export type SourceType = "url" | "api" | "file";
export type SourceScope = "private" | "public";
export type SourceStatus = "pending" | "active" | "error";

export interface CustomSource {
  id: string;
  name: string;
  description?: string;
  sourceType: SourceType;
  domain: string;
  authorityLevel: string;
  scope: SourceScope;
  status: SourceStatus;
  errorMessage?: string;
  lastIndexedAt?: string;
  createdAt: string;
  connectionConfig: {
    url?: string;
    filename?: string;
    mimeType?: string;
    sizeBytes?: number;
    headers?: Record<string, string>;
  };
}

export interface OrgSettings {
  org: {
    id: string;
    name: string;
    apiKey: string;
    plan: string;
    manualReviewMinutesPerClaim: number;
    notificationConfig: {
      emailRecipients: string[];
      webhookUrl?: string;
      notifyOn: string[];
    };
    createdAt: string;
  };
  members: MemberWithStats[];
}

export interface MemberWithStats {
  id: string;
  name: string;
  email: string;
  role: string;
  createdAt: string;
  reviewsCompleted: number;
  avgReviewTimeMs: number;
  approvalRate: number;
  avgFixesApplied: number;
}

export interface DashboardData {
  period: string;
  totalVerifications: number;
  passCount: number;
  flagCount: number;
  blockCount: number;
  totalClaims: number;
  corroboratedCount: number;
  contradictedCount: number;
  unsupportedCount: number;
  outOfScopeCount: number;
  claimsPreventedFromPublication: number;
  avgCoverageRatio: number;
  avgCorroborationRate: number;
  estimatedHoursSaved: number;
  deltas: {
    totalVerifications: number;
    claimsPreventedFromPublication: number;
    avgCorroborationRate: number;
    estimatedHoursSaved: number;
  };
  verificationsByDay: Array<{ date: string; value: number }>;
  decisionByDay: Array<{ date: string; pass: number; flag: number; block: number }>;
  corroborationRateByDay: Array<{ date: string; value: number }>;
  coverageRatioByDay: Array<{ date: string; value: number }>;
  outOfScopeRateByDay: Array<{ date: string; value: number }>;
  byDomain: { pharma: number; legal: number; financial: number; news_editorial: number };
  discrepancyTypeBreakdown: Record<string, number>;
  confirmationStrengthBreakdown: { strong: number; moderate: number; weak: number };
  sourceAuthorityBreakdown: { primary: number; institutional: number; secondary: number; tertiary: number };
  sourceFreshnessBreakdown: { current: number; aging: number; stale: number; deprecated: number };
  agentLeaderboard: AgentLeaderboardEntry[];
  reviewerLeaderboard: ReviewerLeaderboardEntry[];
  topDecisionReasons: Array<{ reason: string; count: number }>;
  recentActivity: RecentActivityItem[];
  pendingReviewCount: number;
  pendingReviewHasBlock: boolean;
  reviewOperations: {
    avgReviewTimeMs: number;
    approvedCount: number;
    rejectedCount: number;
    reVerificationRate: number;
  };
}

export interface AgentLeaderboardEntry {
  id: string;
  name: string;
  domain: string;
  verifications: number;
  corroborationRate: number;
  contradictionRate: number;
  coverageRatio: number;
  lastActive: string | null;
}

export interface ReviewerLeaderboardEntry {
  userId: string;
  name: string;
  reviewsCompleted: number;
  avgReviewTimeMs: number;
  approvalRate: number;
  avgFixesApplied: number;
  reVerifyRate: number;
  lastActive: string | null;
}

export interface RecentActivityItem {
  id: string;
  inputPreview: string;
  domain: string;
  agentName: string | null;
  decision: "pass" | "flag" | "block";
  reviewStatus: string;
  contradictedCount: number;
  corroborationRate: number;
  createdAt: string;
}

export interface AgentCostEntry {
  agentId: string;
  agentName: string;
  verifications: number;
  inputTokensEst: number;
  outputTokensEst: number;
  costUsd: number;
}

export interface ModelCostEntry {
  model: string;
  verifications: number;
  costUsd: number;
}

export interface CostData {
  period: string;
  totalCostUsd: number;
  totalInputTokensEst: number;
  totalOutputTokensEst: number;
  totalVerifications: number;
  avgCostPerVerification: number;
  projectedMonthlyCost: number;
  deltaPercent: number;
  costByDay: Array<{ date: string; costUsd: number }>;
  byAgent: AgentCostEntry[];
  byModel: ModelCostEntry[];
}
