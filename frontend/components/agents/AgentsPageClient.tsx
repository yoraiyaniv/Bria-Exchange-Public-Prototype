"use client";

import { useState } from "react";
import { Agent, agentsApi } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DomainBadge } from "@/components/shared/DomainBadge";
import {
  Plus, Copy, RefreshCw, Trash2, Check, AlertCircle, Key, Terminal, Loader2, Bot,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface AgentsPageClientProps {
  initialAgents: Agent[];
  error: string | null;
  token: string;
}

const MCP_HOST = "mcp.briaexchange.com";

const DOMAIN_OPTIONS = [
  { value: "financial", label: "Financial" },
  { value: "pharma", label: "Pharma" },
  { value: "legal", label: "Legal" },
  { value: "news_editorial", label: "News & Editorial" },
  { value: "auto", label: "Auto-detect" },
];

const PROFILE_OPTIONS = [
  { value: "permissive", label: "Permissive" },
  { value: "moderate", label: "Moderate" },
  { value: "strict", label: "Strict" },
];

export function AgentsPageClient({ initialAgents, error, token }: AgentsPageClientProps) {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDomain, setNewDomain] = useState<string>("auto");
  const [newProfile, setNewProfile] = useState<string>("moderate");

  // Revealed key modal
  const [revealedKey, setRevealedKey] = useState<{ agentId: string; agentName: string; key: string } | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  // Per-agent state
  const [regenerating, setRegenerating] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState<Set<string>>(new Set());
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

  async function createAgent() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const agent = await agentsApi.create(token, {
        name: newName.trim(),
        type: "AI Agent",
        policy: { domain: newDomain, policy_profile: newProfile as "moderate" | "strict" | "permissive" } as Agent["policy"],
      });
      setAgents(prev => [...prev, agent]);
      // Show full key — only time it's ever visible
      if (agent.apiKey) {
        setRevealedKey({ agentId: agent.id, agentName: agent.name, key: agent.apiKey });
      }
      setNewName("");
      setNewDomain("auto");
      setNewProfile("moderate");
      setShowCreate(false);
    } catch {
      toast.error("Failed to create agent");
    } finally {
      setCreating(false);
    }
  }

  async function regenerateKey(agent: Agent) {
    setRegenerating(prev => new Set(prev).add(agent.id));
    try {
      const { apiKey } = await agentsApi.regenerateKey(token, agent.id);
      setRevealedKey({ agentId: agent.id, agentName: agent.name, key: apiKey });
      // Update preview in list
      setAgents(prev => prev.map(a =>
        a.id === agent.id ? { ...a, apiKey: apiKey.slice(0, 12) + "…" } : a
      ));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Failed to regenerate key: ${msg}`);
    } finally {
      setRegenerating(prev => { const s = new Set(prev); s.delete(agent.id); return s; });
    }
  }

  async function deleteAgent(agent: Agent) {
    setDeleting(prev => new Set(prev).add(agent.id));
    try {
      await agentsApi.delete(token, agent.id);
      setAgents(prev => prev.filter(a => a.id !== agent.id));
      toast.success("Agent deleted");
    } catch {
      toast.error("Failed to delete agent");
    } finally {
      setDeleting(prev => { const s = new Set(prev); s.delete(agent.id); return s; });
    }
  }

  function copyToClipboard(text: string) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).catch(() => execCopy(text));
    } else {
      execCopy(text);
    }
  }

  function execCopy(text: string) {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0";
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
  }

  function copyKey(key: string) {
    copyToClipboard(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  }

  function copySnippet(agentId: string, key: string) {
    const snippet = `claude mcp add --transport sse bria-exchange "https://${MCP_HOST}/sse?api_key=${key}"`;
    copyToClipboard(snippet);
    setCopiedSnippet(agentId);
    setTimeout(() => setCopiedSnippet(null), 2000);
    toast.success("Command copied");
  }

  if (error) {
    return (
      <>
        <TopBar title="Agents" />
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
      <TopBar
        title="Agents"
        subtitle="Connect your AI agents to Bria Exchange via MCP"
      />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">

          {/* Header row */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Each agent gets its own API key, policy, and verification history.
            </p>
            <Button size="sm" className="h-8 text-xs gap-1.5" onClick={() => setShowCreate(true)}>
              <Plus className="h-3.5 w-3.5" />
              New Agent
            </Button>
          </div>

          {/* Create form */}
          {showCreate && (
            <div className="border border-border rounded-lg p-4 bg-card space-y-3">
              <p className="text-sm font-medium">New Agent</p>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-3 space-y-1">
                  <Label className="text-xs text-muted-foreground">Name</Label>
                  <Input
                    placeholder="e.g. Finance Reporter Bot"
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && createAgent()}
                    className="h-8 text-xs bg-input border-border"
                    autoFocus
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Domain</Label>
                  <Select value={newDomain} onValueChange={(v) => v && setNewDomain(v)}>
                    <SelectTrigger className="h-8 text-xs bg-input border-border">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border">
                      {DOMAIN_OPTIONS.map(o => (
                        <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Policy Profile</Label>
                  <Select value={newProfile} onValueChange={(v) => v && setNewProfile(v)}>
                    <SelectTrigger className="h-8 text-xs bg-input border-border">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border">
                      {PROFILE_OPTIONS.map(o => (
                        <SelectItem key={o.value} value={o.value} className="text-xs">{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setShowCreate(false)}>
                  Cancel
                </Button>
                <Button size="sm" className="h-7 text-xs" onClick={createAgent} disabled={creating || !newName.trim()}>
                  {creating ? <><Loader2 className="h-3 w-3 mr-1 animate-spin" />Creating…</> : "Create Agent"}
                </Button>
              </div>
            </div>
          )}

          {/* Agent list */}
          {agents.length === 0 && !showCreate ? (
            <div className="border border-dashed border-border rounded-lg p-10 text-center space-y-3">
              <Bot className="h-8 w-8 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">No agents yet</p>
              <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5" onClick={() => setShowCreate(true)}>
                <Plus className="h-3.5 w-3.5" /> Create your first agent
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {agents.map(agent => (
                <div key={agent.id} className="border border-border rounded-lg bg-card overflow-hidden">
                  {/* Agent header */}
                  <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                    <div className="h-7 w-7 rounded-md bg-primary/15 flex items-center justify-center shrink-0">
                      <Bot className="h-3.5 w-3.5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium truncate">{agent.name}</p>
                        <DomainBadge domain={agent.policy?.domain || "auto"} />
                        <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                          {agent.policy?.policy_profile || "moderate"}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Created {new Date(agent.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs gap-1 text-muted-foreground hover:text-foreground"
                        onClick={() => regenerateKey(agent)}
                        disabled={regenerating.has(agent.id)}
                      >
                        {regenerating.has(agent.id)
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <RefreshCw className="h-3 w-3" />}
                        Regenerate Key
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        onClick={() => deleteAgent(agent)}
                        disabled={deleting.has(agent.id)}
                      >
                        {deleting.has(agent.id)
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <Trash2 className="h-3 w-3" />}
                      </Button>
                    </div>
                  </div>

                  {/* API key + MCP snippet */}
                  <div className="px-4 py-3 space-y-2.5">
                    {/* Key preview */}
                    <div className="flex items-center gap-2">
                      <Key className="h-3 w-3 text-muted-foreground shrink-0" />
                      <code className="text-xs text-muted-foreground font-mono flex-1">
                        {agent.apiKey || "No key — click Regenerate Key"}
                      </code>
                    </div>

                    {/* MCP connect snippet */}
                    {agent.apiKey && (
                      <div className="bg-secondary rounded-md px-3 py-2 flex items-center gap-2 group">
                        <Terminal className="h-3 w-3 text-muted-foreground shrink-0" />
                        <code className="text-[11px] font-mono text-muted-foreground flex-1 truncate">
                          claude mcp add --transport sse bria-exchange &quot;https://{MCP_HOST}/sse?api_key=<span className="text-primary">{agent.apiKey}</span>&quot;
                        </code>
                        <button
                          onClick={() => copySnippet(agent.id, agent.apiKey!)}
                          className={cn(
                            "shrink-0 p-1 rounded transition-colors",
                            copiedSnippet === agent.id
                              ? "text-emerald-400"
                              : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {copiedSnippet === agent.id
                            ? <Check className="h-3 w-3" />
                            : <Copy className="h-3 w-3" />}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Revealed key modal */}
      <Dialog open={!!revealedKey} onOpenChange={() => setRevealedKey(null)}>
        <DialogContent className="bg-card border-border max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <Key className="h-4 w-4 text-primary" />
              Agent API Key — {revealedKey?.agentName}
            </DialogTitle>
            <DialogDescription className="text-xs text-amber-400">
              Copy this key now. It will never be shown again.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="bg-secondary rounded-md p-3 flex items-center gap-2">
              <code className="flex-1 text-xs font-mono text-foreground break-all">
                {revealedKey?.key}
              </code>
              <button
                onClick={() => revealedKey && copyKey(revealedKey.key)}
                className={cn(
                  "shrink-0 p-1.5 rounded transition-colors",
                  copiedKey ? "text-emerald-400" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {copiedKey ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>

            <p className="text-xs text-muted-foreground">Connect with Claude Code:</p>
            <div className="bg-secondary rounded-md px-3 py-2">
              <code className="text-[11px] font-mono text-muted-foreground break-all">
                claude mcp add --transport sse bria-exchange &quot;https://{MCP_HOST}/sse?api_key={revealedKey?.key}&quot;
              </code>
            </div>

            <div className="flex gap-2">
              <Button
                className="flex-1 h-8 text-xs"
                onClick={() => {
                  if (revealedKey) copyKey(revealedKey.key);
                }}
              >
                {copiedKey ? <><Check className="h-3.5 w-3.5 mr-1.5" />Copied!</> : <><Copy className="h-3.5 w-3.5 mr-1.5" />Copy Key</>}
              </Button>
              <Button
                variant="outline"
                className="flex-1 h-8 text-xs"
                onClick={() => {
                  if (revealedKey) copySnippet(revealedKey.agentId, revealedKey.key);
                }}
              >
                <Terminal className="h-3.5 w-3.5 mr-1.5" />Copy Command
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
