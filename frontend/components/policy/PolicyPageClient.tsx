"use client";

import { useState } from "react";
import { Agent, ConnectedSource, PolicyConfig, agentsApi, verifyApi, VerificationResponse } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { DecisionBadge, StatusBadge } from "@/components/shared/DecisionBadge";
import { Plus, Loader2, RefreshCw, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface PolicyPageClientProps {
  initialAgents: Agent[];
  connectedSources: ConnectedSource[];
  error: string | null;
  token: string;
}

const DOMAIN_STARTERS: Record<string, string> = {
  financial: "Company Q3 revenue reached $4.2 billion, exceeding analyst estimates by 8%. The Federal Reserve maintained its target rate at 5.25-5.50% at the November meeting, citing persistent core inflation of 3.4%.",
  legal: "The Supreme Court ruled 6-3 that the regulatory agency exceeded its statutory authority in mandating emissions standards. The decision, which builds on the major questions doctrine, will require Congressional authorization for future EPA rulemaking.",
  pharma: "The drug demonstrated 78% efficacy in Phase III trials with 4,200 patients enrolled across 12 countries. FDA approved the treatment for second-line therapy in metastatic non-small cell lung cancer in November 2023.",
  news_editorial: "International trade volumes declined 4.5% year-over-year in Q2 2024, the largest contraction since 2020. Central banks in G7 nations have coordinated to maintain liquidity provisions through Q3.",
};

type Domain = "pharma" | "legal" | "financial" | "news_editorial";

const DEFAULT_POLICY: PolicyConfig = {
  unsupported_policy: "flag",
  out_of_scope_policy: "flag",
  contradiction_policy: "flag",
  flag_extrapolations: true,
  require_acknowledgement_note: false,
  domain: "news_editorial",
  policy_profile: "moderate",
  connectedSourceIds: [],
};

export function PolicyPageClient({ initialAgents, connectedSources, error, token }: PolicyPageClientProps) {
  const [agents, setAgents] = useState(initialAgents);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(initialAgents[0]?.id || null);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newAgentName, setNewAgentName] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Sandbox state
  const [sandboxText, setSandboxText] = useState("");
  const [sandboxRunning, setSandboxRunning] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<VerificationResponse | null>(null);
  const [expandedClaims, setExpandedClaims] = useState<Set<number>>(new Set());

  const selectedAgent = agents.find(a => a.id === selectedAgentId);
  const [editedPolicy, setEditedPolicy] = useState<PolicyConfig>(
    selectedAgent?.policy || DEFAULT_POLICY
  );

  function selectAgent(agent: Agent) {
    setSelectedAgentId(agent.id);
    setEditedPolicy(agent.policy);
    setSandboxResult(null);
  }

  function updatePolicy<K extends keyof PolicyConfig>(key: K, value: PolicyConfig[K]) {
    if (key === "contradiction_policy" && value === "accept") return; // hard constraint
    setEditedPolicy(prev => ({ ...prev, [key]: value }));
  }

  async function savePolicy() {
    if (!selectedAgentId) return;
    setSaving(true);
    try {
      const updated = await agentsApi.update(token, selectedAgentId, { policy: editedPolicy });
      setAgents(prev => prev.map(a => a.id === selectedAgentId ? { ...a, ...updated } : a));
      toast.success("Policy saved");
    } catch {
      toast.error("Failed to save policy");
    } finally {
      setSaving(false);
    }
  }

  async function createAgent() {
    if (!newAgentName.trim()) return;
    setCreating(true);
    try {
      const agent = await agentsApi.create(token, {
        name: newAgentName,
        type: "AI Agent",
        policy: editedPolicy,
      });
      setAgents(prev => [...prev, agent]);
      setSelectedAgentId(agent.id);
      setEditedPolicy(agent.policy);
      setNewAgentName("");
      setShowCreateForm(false);
      toast.success("Agent created");
    } catch {
      toast.error("Failed to create agent");
    } finally {
      setCreating(false);
    }
  }

  async function runSandbox() {
    if (!sandboxText.trim()) return;
    setSandboxRunning(true);
    setSandboxResult(null);
    try {
      const result = await verifyApi.run(token, {
        text: sandboxText,
        config: editedPolicy,
        agentId: selectedAgentId || undefined,
      }) as VerificationResponse;
      setSandboxResult(result);
    } catch {
      toast.error("Verification failed");
    } finally {
      setSandboxRunning(false);
    }
  }

  if (error) {
    return (
      <>
        <TopBar title="Policy Manager" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Policy Manager" subtitle="Configure verification policies and test in the sandbox" />

      <div className="flex-1 flex divide-x divide-border min-h-0">
        {/* Left: Agent list */}
        <div className="w-[200px] flex flex-col bg-card overflow-y-auto shrink-0">
          <div className="p-3 border-b border-border">
            <Button
              size="sm"
              variant="outline"
              className="w-full gap-1.5 text-xs h-7"
              onClick={() => setShowCreateForm(!showCreateForm)}
            >
              <Plus className="h-3 w-3" />
              New Agent
            </Button>
            {showCreateForm && (
              <div className="mt-2 space-y-1.5">
                <Input
                  placeholder="Agent name"
                  value={newAgentName}
                  onChange={e => setNewAgentName(e.target.value)}
                  className="h-7 text-xs bg-input border-border"
                  onKeyDown={e => e.key === "Enter" && createAgent()}
                />
                <Button size="sm" className="w-full h-6 text-xs" onClick={createAgent} disabled={creating}>
                  {creating ? "Creating..." : "Create"}
                </Button>
              </div>
            )}
          </div>

          <div className="flex-1 py-1">
            {agents.length === 0 ? (
              <p className="text-[11px] text-muted-foreground px-3 py-4 text-center">No agents yet</p>
            ) : (
              agents.map(agent => (
                <button
                  key={agent.id}
                  onClick={() => selectAgent(agent)}
                  className={cn(
                    "w-full flex flex-col items-start gap-0.5 px-3 py-2.5 text-left transition-colors text-xs",
                    selectedAgentId === agent.id
                      ? "bg-primary/15 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                  )}
                >
                  <span className="font-medium truncate w-full">{agent.name}</span>
                  <DomainBadge domain={agent.policy?.domain || "news_editorial"} />
                </button>
              ))
            )}
          </div>
        </div>

        {/* Center: Policy editor */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 min-w-0">
          {!selectedAgent ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Select or create an agent to configure its policy
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">{selectedAgent.name}</h2>
                <Button size="sm" className="h-7 text-xs" onClick={savePolicy} disabled={saving}>
                  {saving ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Saving...</> : "Save Policy"}
                </Button>
              </div>

              {/* Profile preset */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Policy Profile</Label>
                <Tabs
                  value={editedPolicy.policy_profile}
                  onValueChange={(v) => {
                    const profiles: Record<string, Partial<PolicyConfig>> = {
                      strict: { unsupported_policy: "block", out_of_scope_policy: "block", contradiction_policy: "block", flag_extrapolations: true, require_acknowledgement_note: true },
                      moderate: { unsupported_policy: "flag", out_of_scope_policy: "flag", contradiction_policy: "flag", flag_extrapolations: true, require_acknowledgement_note: false },
                      permissive: { unsupported_policy: "accept", out_of_scope_policy: "accept", contradiction_policy: "flag", flag_extrapolations: false, require_acknowledgement_note: false },
                    };
                    setEditedPolicy(prev => ({ ...prev, policy_profile: v as PolicyConfig["policy_profile"], ...profiles[v] }));
                  }}
                >
                  <TabsList className="bg-secondary h-8">
                    <TabsTrigger value="permissive" className="text-xs">Permissive</TabsTrigger>
                    <TabsTrigger value="moderate" className="text-xs">Moderate</TabsTrigger>
                    <TabsTrigger value="strict" className="text-xs">Strict</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              {/* Domain */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Domain</Label>
                <Select value={editedPolicy.domain} onValueChange={v => updatePolicy("domain", v as Domain)}>
                  <SelectTrigger className="h-8 text-xs bg-input border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border">
                    <SelectItem value="pharma" className="text-xs">Pharma</SelectItem>
                    <SelectItem value="legal" className="text-xs">Legal</SelectItem>
                    <SelectItem value="financial" className="text-xs">Financial</SelectItem>
                    <SelectItem value="news_editorial" className="text-xs">News & Editorial</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Policy toggles */}
              <div className="space-y-3">
                <Label className="text-xs text-muted-foreground">Claim Policies</Label>

                {([
                  { key: "contradiction_policy" as const, label: "Contradiction policy", options: ["flag", "block"], note: "accept is never allowed — contradictions are always surfaced" },
                  { key: "unsupported_policy" as const, label: "Unsupported policy", options: ["accept", "flag", "block"], note: null },
                  { key: "out_of_scope_policy" as const, label: "Out-of-scope policy", options: ["accept", "flag", "block"], note: null },
                ] as const).map(field => (
                  <div key={field.key} className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">{field.label}</p>
                      {field.note && <p className="text-[10px] text-muted-foreground">{field.note}</p>}
                    </div>
                    <Select
                      value={editedPolicy[field.key]}
                      onValueChange={v => updatePolicy(field.key, v as "accept" | "flag" | "block")}
                    >
                      <SelectTrigger className="h-7 w-24 text-xs bg-input border-border">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-card border-border">
                        {field.options.map(opt => (
                          <SelectItem key={opt} value={opt} className="text-xs">{opt}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>

              {/* Switches */}
              <div className="space-y-3">
                <Label className="text-xs text-muted-foreground">Options</Label>
                {([
                  { key: "flag_extrapolations" as const, label: "Flag extrapolations", desc: "Flag claims where AI overstates beyond source evidence" },
                  { key: "require_acknowledgement_note" as const, label: "Require justification note", desc: "Reviewers must write a note before acknowledging risks (recommended for pharma/legal)" },
                ] as const).map(sw => (
                  <div key={sw.key} className="flex items-center justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-xs font-medium">{sw.label}</p>
                      <p className="text-[10px] text-muted-foreground">{sw.desc}</p>
                    </div>
                    <Switch
                      checked={editedPolicy[sw.key]}
                      onCheckedChange={v => updatePolicy(sw.key, v)}
                    />
                  </div>
                ))}
              </div>

              {/* Connected sources for this agent */}
              {connectedSources.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Connected Sources</Label>
                  <div className="space-y-1">
                    {connectedSources.filter(s => s.domain === editedPolicy.domain || s.status === "active").map(src => {
                      const isEnabled = editedPolicy.connectedSourceIds?.includes(src.id) || false;
                      return (
                        <label key={src.id} className="flex items-center gap-2.5 text-xs cursor-pointer hover:bg-secondary rounded px-2 py-1.5">
                          <input
                            type="checkbox"
                            checked={isEnabled}
                            onChange={e => {
                              const ids = editedPolicy.connectedSourceIds || [];
                              updatePolicy("connectedSourceIds", e.target.checked ? [...ids, src.id] : ids.filter(id => id !== src.id));
                            }}
                            className="rounded"
                          />
                          <span>{src.name}</span>
                          <span className="text-muted-foreground">({src.authorityLevel})</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Right: Sandbox */}
        <div className="w-[420px] flex flex-col overflow-y-auto bg-secondary/20 shrink-0">
          <div className="p-4 border-b border-border">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Sandbox</h3>

            {/* Domain starters */}
            <div className="flex gap-1.5 mb-3 flex-wrap">
              {Object.keys(DOMAIN_STARTERS).map(domain => (
                <button
                  key={domain}
                  onClick={() => setSandboxText(DOMAIN_STARTERS[domain])}
                  className="text-[10px] px-2 py-1 rounded bg-secondary hover:bg-border transition-colors text-muted-foreground hover:text-foreground"
                >
                  {domain === "news_editorial" ? "News & Ed." : domain.charAt(0).toUpperCase() + domain.slice(1)}
                </button>
              ))}
            </div>

            <textarea
              value={sandboxText}
              onChange={e => setSandboxText(e.target.value)}
              placeholder="Paste AI-generated text to verify against the current policy..."
              className="w-full h-32 text-xs bg-input border border-border rounded p-2.5 text-foreground placeholder-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary"
            />

            <Button
              className="w-full mt-2 h-8 text-xs gap-1.5"
              onClick={runSandbox}
              disabled={sandboxRunning || !sandboxText.trim()}
            >
              {sandboxRunning ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying...</>
              ) : (
                <>Run Sandbox</>
              )}
            </Button>
          </div>

          {/* Sandbox results */}
          {sandboxResult && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Decision banner */}
              <div className={cn("flex items-center justify-between px-3 py-2 rounded-lg border text-xs", {
                "bg-emerald-500/10 border-emerald-500/30": sandboxResult.decision === "pass",
                "bg-amber-500/10 border-amber-500/30": sandboxResult.decision === "flag",
                "bg-red-500/10 border-red-500/30": sandboxResult.decision === "block",
              })}>
                <DecisionBadge decision={sandboxResult.decision} size="md" />
                <span className="text-muted-foreground">
                  {sandboxResult.audit.processing_time_ms}ms · {sandboxResult.coverage.total_claims} claims
                </span>
              </div>

              {/* Coverage */}
              <div className="grid grid-cols-4 gap-1.5 text-center">
                {[
                  { label: "Corroborated", v: sandboxResult.coverage.corroborated, color: "text-emerald-400" },
                  { label: "Contradicted", v: sandboxResult.coverage.contradicted, color: "text-red-400" },
                  { label: "Unsupported", v: sandboxResult.coverage.unsupported, color: "text-amber-400" },
                  { label: "OOS", v: sandboxResult.coverage.out_of_scope, color: "text-muted-foreground" },
                ].map(s => (
                  <div key={s.label} className="bg-secondary rounded p-1.5">
                    <p className={`text-sm font-bold font-mono ${s.color}`}>{s.v}</p>
                    <p className="text-[9px] text-muted-foreground">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Claim breakdown */}
              <div className="space-y-1.5">
                {sandboxResult.sentences.flatMap(s => s.claims).map((claim, i) => {
                  const isExpanded = expandedClaims.has(i);
                  return (
                    <div key={i} className="border border-border rounded overflow-hidden">
                      <button
                        onClick={() => {
                          const next = new Set(expandedClaims);
                          isExpanded ? next.delete(i) : next.add(i);
                          setExpandedClaims(next);
                        }}
                        className="w-full flex items-center gap-2 p-2 text-left hover:bg-secondary/50 transition-colors"
                      >
                        <StatusBadge status={claim.status} size="sm" />
                        <p className="flex-1 text-[11px] truncate">{claim.text.slice(0, 80)}</p>
                        {isExpanded ? <ChevronUp className="h-3 w-3 text-muted-foreground" /> : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
                      </button>
                      {isExpanded && (
                        <div className="border-t border-border p-2 space-y-2 text-[11px] bg-secondary/20">
                          {claim.sources.map((src, si) => (
                            <div key={si} className="space-y-1">
                              <p className="text-muted-foreground font-medium">{src.name} · {src.authority_level} · {src.freshness}</p>
                              <p className="text-foreground">{src.detail.source_states}</p>
                              {src.detail.discrepancy_type && (
                                <p className="text-amber-400 text-[10px]">Type: {src.detail.discrepancy_type}</p>
                              )}
                            </div>
                          ))}
                          {claim.fix && "suggestion" in claim.fix && (
                            <p className="text-primary text-[10px] pt-1 border-t border-border">{claim.fix.suggestion}</p>
                          )}
                          {claim.fix && "suggested_text" in claim.fix && claim.fix.suggested_text && (
                            <p className="text-primary text-[10px] pt-1 border-t border-border">{claim.fix.suggested_text}</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
