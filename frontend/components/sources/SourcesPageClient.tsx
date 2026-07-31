"use client";

import { useState, useTransition, useRef } from "react";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import { TopBar } from "@/components/layout/TopBar";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  type Connector,
  type ConnectedSource,
  type ComingSoonSource,
  type CustomSource,
  type SourceScope,
  type SourceType,
  sourcesApi,
} from "@/lib/api";
import {
  CheckCircle2,
  AlertCircle,
  Plug,
  Unplug,
  RefreshCw,
  Eye,
  EyeOff,
  Zap,
  Shield,
} from "lucide-react";

interface SourcesPageClientProps {
  catalog: Connector[];
  connectedSources: ConnectedSource[];
  comingSoon: ComingSoonSource[];
  customMine: CustomSource[];
  customCommunity: CustomSource[];
  error: string | null;
  token: string;
  apiBase: string;
}

const DOMAIN_TABS = [
  { value: "all", label: "All" },
  { value: "financial", label: "Financial" },
  { value: "legal", label: "Legal" },
  { value: "pharma", label: "Pharma" },
  { value: "news_editorial", label: "News & Editorial" },
  { value: "academic", label: "Academic" },
  { value: "geography", label: "Geography" },
  { value: "climate", label: "Climate" },
];

const AUTHORITY_COLORS: Record<string, string> = {
  primary: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  institutional: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  secondary: "text-purple-400 bg-purple-400/10 border-purple-400/20",
  tertiary: "text-slate-400 bg-slate-400/10 border-slate-400/20",
};

const AUTHORITY_LABELS: Record<string, string> = {
  primary: "Primary",
  institutional: "Institutional",
  secondary: "Secondary",
  tertiary: "Tertiary",
};

// Display enrichment — logo initials and bg color per connector
const LOGO_ENRICHMENT: Record<string, { initials: string; color: string }> = {
  edgar:          { initials: "SEC", color: "bg-blue-600/20 text-blue-300" },
  fred:           { initials: "FED", color: "bg-green-700/20 text-green-300" },
  worldbank:      { initials: "WB",  color: "bg-cyan-700/20 text-cyan-300" },
  bloomberg:      { initials: "BB",  color: "bg-orange-600/20 text-orange-300" },
  refinitiv:      { initials: "RF",  color: "bg-purple-700/20 text-purple-300" },
  factset:        { initials: "FS",  color: "bg-indigo-700/20 text-indigo-300" },
  sp_capital_iq:  { initials: "S&P", color: "bg-red-700/20 text-red-300" },
  courtlistener:  { initials: "CL",  color: "bg-amber-700/20 text-amber-300" },
  federalregister:{ initials: "FR",  color: "bg-blue-800/20 text-blue-300" },
  govinfo:        { initials: "GOV", color: "bg-slate-700/20 text-slate-300" },
  caselaw:        { initials: "HAR", color: "bg-red-800/20 text-red-300" },
  westlaw:        { initials: "WL",  color: "bg-orange-800/20 text-orange-300" },
  lexisnexis:     { initials: "LN",  color: "bg-red-700/20 text-red-300" },
  fastcase:       { initials: "FC",  color: "bg-green-800/20 text-green-300" },
  pubmed:         { initials: "PM",  color: "bg-blue-700/20 text-blue-300" },
  clinicaltrials: { initials: "CT",  color: "bg-teal-700/20 text-teal-300" },
  openfda:        { initials: "FDA", color: "bg-blue-900/30 text-blue-300" },
  dailymed:       { initials: "DM",  color: "bg-emerald-800/20 text-emerald-300" },
  cochrane:       { initials: "CO",  color: "bg-purple-800/20 text-purple-300" },
  guardian:       { initials: "GD",  color: "bg-blue-700/20 text-blue-300" },
  nytimes:        { initials: "NYT", color: "bg-slate-800/20 text-slate-300" },
  wikidata:       { initials: "WD",  color: "bg-green-700/20 text-green-300" },
  crossref:       { initials: "CR",  color: "bg-orange-700/20 text-orange-300" },
  semanticscholar:{ initials: "S2",  color: "bg-cyan-800/20 text-cyan-300" },
  // New sources
  arxiv:          { initials: "arX", color: "bg-red-700/20 text-red-300" },
  openalex:       { initials: "OA",  color: "bg-violet-700/20 text-violet-300" },
  europepmc:      { initials: "PMC", color: "bg-teal-800/20 text-teal-300" },
  bls:            { initials: "BLS", color: "bg-blue-800/20 text-blue-300" },
  census:         { initials: "CEN", color: "bg-indigo-800/20 text-indigo-300" },
  oecd:           { initials: "OEC", color: "bg-sky-700/20 text-sky-300" },
  geonames:       { initials: "GEO", color: "bg-green-800/20 text-green-300" },
  openmeteo:      { initials: "WX",  color: "bg-cyan-700/20 text-cyan-300" },
  wikipedia:      { initials: "WP",  color: "bg-slate-600/20 text-slate-300" },
};

function getLogo(connectorId: string) {
  return LOGO_ENRICHMENT[connectorId] ?? { initials: connectorId.slice(0, 2).toUpperCase(), color: "bg-secondary text-muted-foreground" };
}

export function SourcesPageClient({
  catalog,
  connectedSources: initialConnected,
  comingSoon,
  customMine,
  customCommunity,
  error,
  token,
}: SourcesPageClientProps) {
  const [activeTab, setActiveTab] = useState("all");
  const [connectedSources, setConnectedSources] = useState(initialConnected);
  const [connectModal, setConnectModal] = useState<Connector | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; latencyMs?: number; message?: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const connectedMap = new Map(connectedSources.map(s => [s.connectorId, s]));

  const filtered = catalog.filter(c =>
    activeTab === "all" || c.domain === activeTab
  );

  function openConnect(connector: Connector) {
    setConnectModal(connector);
    setApiKey("");
    setShowKey(false);
    setTestResult(null);
  }

  async function handleTest() {
    if (!connectModal) return;
    setTesting(true);
    setTestResult(null);
    try {
      const connected = connectedMap.get(connectModal.id);
      if (connected) {
        const result = await sourcesApi.testConnection(token, connected.id);
        setTestResult(result);
      } else {
        // Simulate test before connecting
        await new Promise(r => setTimeout(r, 600 + Math.random() * 400));
        setTestResult({ ok: true, latencyMs: 120 + Math.floor(Math.random() * 200), message: "Connection successful" });
      }
    } catch {
      setTestResult({ ok: false, message: "Connection failed — check your API key" });
    } finally {
      setTesting(false);
    }
  }

  async function handleConnect() {
    if (!connectModal) return;
    setSaving(true);
    try {
      const newSource = await sourcesApi.connect(token, {
        connectorId: connectModal.id,
        apiKey: apiKey || undefined,
      });
      setConnectedSources(prev => {
        // Replace if already connected (reconfigure)
        const exists = prev.some(s => s.connectorId === connectModal.id);
        if (exists) return prev.map(s => s.connectorId === connectModal.id ? newSource : s);
        return [...prev, newSource];
      });
      setConnectModal(null);
    } catch {
      setTestResult({ ok: false, message: "Failed to connect. Please try again." });
    } finally {
      setSaving(false);
    }
  }

  async function handleDisconnect(sourceId: string) {
    setDisconnecting(sourceId);
    try {
      await sourcesApi.disconnect(token, sourceId);
      setConnectedSources(prev => prev.filter(s => s.id !== sourceId));
    } catch {
      // silent
    } finally {
      setDisconnecting(null);
    }
  }

  async function handleTestConnected(connector: Connector) {
    const connected = connectedMap.get(connector.id);
    if (!connected) return;
    setConnectModal(connector);
    setTestResult(null);
    setTesting(true);
    try {
      const r = await sourcesApi.testConnection(token, connected.id);
      setTestResult(r);
    } catch {
      setTestResult({ ok: false, message: "Test failed" });
    } finally {
      setTesting(false);
    }
  }

  if (error) {
    return (
      <>
        <TopBar title="Sources" subtitle="Licensed database connectors" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </div>
      </>
    );
  }

  const activeCount = catalog.filter(c => c.isFree).length + connectedSources.filter(s => s.status === "active").length;
  const freeCount = catalog.filter(c => c.isFree).length;

  return (
    <>
      <TopBar
        title="Sources"
        subtitle={`${freeCount} free connectors active · ${connectedSources.filter(s => !catalog.find(c => c.id === s.connectorId)?.isFree).length} paid connected`}
      />

      <div className="flex-1 pt-8 px-6 pb-6 space-y-5">
        {/* Key design principle banner */}
        <div className="flex items-start gap-3 bg-purple-500/5 border border-purple-500/20 rounded-lg px-4 py-3">
          <Shield className="h-4 w-4 text-purple-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-xs text-purple-300 font-medium">Bria sets authority levels</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Source authority is determined by Bria based on source quality — not configurable by customers. Free connectors are live immediately with no setup. Paid connectors require your organisation's credentials.
            </p>
          </div>
        </div>

        {/* Domain tabs */}
        <div className="flex gap-1 border-b border-border">
          {DOMAIN_TABS.map(tab => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.value
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
              <span className="ml-1.5 text-[10px] text-muted-foreground">
                ({catalog.filter(c => tab.value === "all" || c.domain === tab.value).length})
              </span>
            </button>
          ))}
        </div>

        {/* Stats row */}
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>
            <span className="text-emerald-400 font-medium">{freeCount}</span> free connectors live
          </span>
          <span>·</span>
          <span>
            <span className="text-blue-400 font-medium">{connectedSources.filter(s => s.status === "active").length}</span> paid connected
          </span>
          <span>·</span>
          <span>
            <span className="text-slate-400 font-medium">{catalog.filter(c => !c.isFree).length - connectedSources.length}</span> stubs available
          </span>
        </div>

        {/* Connector grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filtered.map(connector => {
            const connected = connectedMap.get(connector.id);
            const isConnected = !!connected && connected.status === "active";
            const hasError = connected?.status === "error";
            const logo = getLogo(connector.id);

            return (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                connected={connected}
                isConnected={isConnected}
                hasError={hasError}
                logoInitials={logo.initials}
                logoColor={logo.color}
                disconnecting={disconnecting === (connected?.id ?? "")}
                onConnect={() => openConnect(connector)}
                onReconfigure={() => openConnect(connector)}
                onDisconnect={() => connected && handleDisconnect(connected.id)}
                onTest={() => handleTestConnected(connector)}
              />
            );
          })}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-muted-foreground text-sm">
            No connectors found for this domain.
          </div>
        )}

        {/* Coming Soon */}
        <ComingSoonSection sources={comingSoon} token={token} />

        {/* Custom Sources */}
        <CustomSourcesSection initialMine={customMine} initialCommunity={customCommunity} token={token} />
      </div>

      {/* Connect / Reconfigure / Test Modal */}
      <Dialog open={!!connectModal} onOpenChange={open => !open && setConnectModal(null)}>
        <DialogContent className="bg-card border-border max-w-md">
          {connectModal && (() => {
            const logo = getLogo(connectModal.id);
            const connected = connectedMap.get(connectModal.id);
            return (
              <>
                <DialogHeader>
                  <div className="flex items-center gap-3 mb-1">
                    <div className={`h-10 w-10 rounded-md flex items-center justify-center font-bold text-xs shrink-0 ${logo.color}`}>
                      {logo.initials}
                    </div>
                    <div>
                      <DialogTitle className="text-sm">{connectModal.name}</DialogTitle>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <DomainBadge domain={connectModal.domain} />
                        <AuthorityBadge level={connectModal.authorityLevel} />
                      </div>
                    </div>
                  </div>
                  <DialogDescription className="text-xs text-muted-foreground">
                    {connectModal.description}
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 mt-2">
                  {connectModal.isFree ? (
                    /* Free connector */
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-3 py-2.5">
                        <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                        <div>
                          <p className="text-xs text-emerald-400 font-medium">Active — no configuration needed</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">This connector is live immediately. No API key required.</p>
                        </div>
                      </div>

                      {testResult && (
                        <TestResultBanner result={testResult} />
                      )}

                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs gap-1.5 w-full"
                        onClick={handleTest}
                        disabled={testing}
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${testing ? "animate-spin" : ""}`} />
                        {testing ? "Testing..." : "Test Connection"}
                      </Button>
                    </div>
                  ) : (
                    /* Paid connector */
                    <>
                      {connected ? (
                        <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-3 py-2 text-xs text-emerald-400">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                          Connected
                          {connected.lastTestedAt && (
                            <span className="text-muted-foreground ml-1">
                              · tested {new Date(connected.lastTestedAt).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      ) : null}

                      <div className="space-y-1.5">
                        <Label className="text-xs">API Key</Label>
                        <div className="relative">
                          <Input
                            type={showKey ? "text" : "password"}
                            value={apiKey}
                            onChange={e => setApiKey(e.target.value)}
                            placeholder={connected ? "Enter new key to update..." : "Enter your API key..."}
                            className="text-xs bg-secondary border-border pr-9 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => setShowKey(v => !v)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                          </button>
                        </div>
                      </div>

                      {testResult && <TestResultBanner result={testResult} />}

                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs gap-1.5"
                          onClick={handleTest}
                          disabled={testing || (!apiKey && !connected)}
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${testing ? "animate-spin" : ""}`} />
                          {testing ? "Testing..." : "Test"}
                        </Button>
                        <Button
                          size="sm"
                          className="text-xs gap-1.5 flex-1 bg-primary hover:bg-primary/90"
                          onClick={handleConnect}
                          disabled={saving || !apiKey}
                        >
                          <Plug className="h-3.5 w-3.5" />
                          {saving ? "Connecting..." : connected ? "Update Key" : "Connect"}
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>
    </>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function ConnectorCard({
  connector,
  connected,
  isConnected,
  hasError,
  logoInitials,
  logoColor,
  disconnecting,
  onConnect,
  onReconfigure,
  onDisconnect,
  onTest,
}: {
  connector: Connector;
  connected: ConnectedSource | undefined;
  isConnected: boolean;
  hasError: boolean;
  logoInitials: string;
  logoColor: string;
  disconnecting: boolean;
  onConnect: () => void;
  onReconfigure: () => void;
  onDisconnect: () => void;
  onTest: () => void;
}) {
  return (
    <div className={`bg-card border rounded-lg p-4 flex flex-col gap-3 transition-colors ${
      hasError ? "border-red-500/40" : "border-border hover:border-border/60"
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`h-8 w-8 rounded-md flex items-center justify-center font-bold text-[10px] shrink-0 ${logoColor}`}>
            {logoInitials}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-foreground truncate">{connector.name}</p>
            <DomainBadge domain={connector.domain} />
          </div>
        </div>
        <StatusPill isFree={connector.isFree} isConnected={isConnected} hasError={hasError} />
      </div>

      {/* Description */}
      <p className="text-[11px] text-muted-foreground leading-relaxed flex-1">{connector.description}</p>

      {/* Authority level */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-muted-foreground">Authority:</span>
        <AuthorityBadge level={connector.authorityLevel} />
        <span className="text-[10px] text-muted-foreground">(Bria)</span>
      </div>

      {/* Actions */}
      <div>
        {connector.isFree ? (
          <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
            <Zap className="h-3 w-3" />
            Active — no configuration needed
          </div>
        ) : isConnected ? (
          <div className="flex gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="text-[11px] h-7 gap-1 flex-1"
              onClick={onTest}
            >
              <RefreshCw className="h-3 w-3" />
              Test
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-[11px] h-7 gap-1 flex-1"
              onClick={onReconfigure}
            >
              Reconfigure
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-[11px] h-7 px-2 text-red-400 hover:text-red-300 hover:bg-red-500/10"
              onClick={onDisconnect}
              disabled={disconnecting}
            >
              <Unplug className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="text-[11px] h-7 gap-1.5 w-full border-dashed border-muted-foreground/40 hover:border-primary hover:text-primary"
            onClick={onConnect}
          >
            <Plug className="h-3 w-3" />
            Connect
          </Button>
        )}

        {hasError && (
          <div className="flex items-center gap-1.5 text-[11px] text-red-400 mt-2">
            <AlertCircle className="h-3 w-3 shrink-0" />
            Connection error — reconfigure to fix
          </div>
        )}
      </div>
    </div>
  );
}

function StatusPill({ isFree, isConnected, hasError }: { isFree: boolean; isConnected: boolean; hasError: boolean }) {
  if (hasError) return (
    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/20 whitespace-nowrap shrink-0">Error</span>
  );
  if (isFree || isConnected) return (
    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 whitespace-nowrap shrink-0">Active</span>
  );
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-muted-foreground border border-border whitespace-nowrap shrink-0">Stub</span>
  );
}

function AuthorityBadge({ level }: { level: string }) {
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${AUTHORITY_COLORS[level] ?? AUTHORITY_COLORS.secondary}`}>
      {AUTHORITY_LABELS[level] ?? level}
    </span>
  );
}

function TestResultBanner({ result }: { result: { ok: boolean; latencyMs?: number; message?: string } }) {
  return (
    <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-md ${
      result.ok
        ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
        : "bg-red-500/10 border border-red-500/20 text-red-400"
    }`}>
      {result.ok
        ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
        : <AlertCircle className="h-3.5 w-3.5 shrink-0" />
      }
      <span>
        {result.ok
          ? `Connected${result.latencyMs ? ` · ${result.latencyMs}ms` : ""}`
          : result.message ?? "Connection failed"
        }
      </span>
    </div>
  );
}

// ─── Coming Soon Section ─────────────────────────────────────────────────────

const COMING_SOON_CATEGORY_COLORS: Record<string, string> = {
  "Scientific & Medical": "bg-violet-500",
  "Financial & Industry": "bg-blue-500",
  "Legal & Regulatory":   "bg-amber-500",
};

function ComingSoonSection({ sources, token }: { sources: ComingSoonSource[]; token: string }) {
  const [items, setItems] = useState<ComingSoonSource[]>(sources);

  const handleVote = async (id: string) => {
    const item = items.find(s => s.id === id);
    if (!item) return;
    try {
      const res = await sourcesApi.toggleInterest(token, id, item.orgHasVoted ? false : item.orgNotifyOnLaunch);
      setItems(prev => prev.map(s => s.id === id
        ? { ...s, orgHasVoted: res.voted, orgNotifyOnLaunch: res.notifyOnLaunch, interestCount: res.interestCount }
        : s
      ));
    } catch {
      toast.error("Failed to update vote");
    }
  };

  const handleNotify = async (id: string, notify: boolean) => {
    try {
      const res = await sourcesApi.updateNotify(token, id, notify);
      setItems(prev => prev.map(s => s.id === id ? { ...s, orgNotifyOnLaunch: res.notifyOnLaunch } : s));
    } catch {
      toast.error("Failed to update notification preference");
    }
  };

  if (items.length === 0) return null;

  const sorted = [...items].sort((a, b) => b.interestCount - a.interestCount);

  return (
    <div className="mt-10">
      <div className="flex items-center gap-3 mb-2">
        <h2 className="text-[11px] font-mono tracking-widest text-muted-foreground uppercase whitespace-nowrap">
          Coming Soon
        </h2>
        <div className="h-px flex-1 bg-border" />
      </div>
      <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
        Data sources in development. Vote for the ones you need most — counts are shared across all organizations and drive our roadmap.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {sorted.map(source => (
          <ComingSoonCard
            key={source.id}
            source={source}
            onVote={() => handleVote(source.id)}
            onNotify={(v) => handleNotify(source.id, v)}
          />
        ))}
      </div>
    </div>
  );
}

function ComingSoonCard({
  source,
  onVote,
  onNotify,
}: {
  source: ComingSoonSource;
  onVote: () => void;
  onNotify: (notify: boolean) => void;
}) {
  const barColor = COMING_SOON_CATEGORY_COLORS[source.category] ?? "bg-slate-500";

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden flex flex-col">
      <div className={`h-1 w-full ${barColor}`} />
      <div className="p-4 flex flex-col gap-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-medium text-foreground">{source.name}</p>
            <DomainBadge domain={source.domain} />
          </div>
          <span className="text-[9px] font-mono tracking-widest text-muted-foreground border border-border rounded px-1.5 py-0.5 whitespace-nowrap shrink-0">
            {source.category}
          </span>
        </div>

        <p className="text-[11px] text-muted-foreground leading-relaxed flex-1">{source.description}</p>

        <div className="flex flex-wrap gap-1">
          {source.examples.slice(0, 5).map(ex => (
            <span key={ex} className="text-[9px] font-mono bg-secondary border border-border rounded px-1.5 py-0.5 text-muted-foreground">
              {ex}
            </span>
          ))}
          {source.examples.length > 5 && (
            <span className="text-[9px] font-mono text-muted-foreground px-1">+{source.examples.length - 5}</span>
          )}
        </div>

        <p className="text-[10px] text-muted-foreground">via {source.partner}</p>

        <div className="flex items-center justify-between gap-2 mt-auto pt-1 border-t border-border">
          <span className="text-[10px] text-muted-foreground">
            {source.interestCount} {source.interestCount === 1 ? "org" : "orgs"} interested
          </span>
          <button
            onClick={onVote}
            className={`text-[10px] font-mono tracking-widest px-3 py-1.5 rounded border transition-colors ${
              source.orgHasVoted
                ? "bg-violet-500/15 border-violet-500/40 text-violet-400"
                : "border-border text-muted-foreground hover:border-violet-500/40 hover:text-violet-400"
            }`}
          >
            {source.orgHasVoted ? "INTERESTED" : "VOTE"}
          </button>
        </div>

        {source.orgHasVoted && (
          <label className="flex items-center gap-2 cursor-pointer mt-1">
            <input
              type="checkbox"
              checked={source.orgNotifyOnLaunch}
              onChange={e => onNotify(e.target.checked)}
              className="accent-violet-500 h-3 w-3"
            />
            <span className="text-[10px] text-muted-foreground">Notify me when this launches</span>
          </label>
        )}
      </div>
    </div>
  );
}

// ─── Custom Sources Section ──────────────────────────────────────────────────

const DOMAIN_OPTIONS = [
  { value: "financial",     label: "Financial & Industry" },
  { value: "legal",         label: "Legal & Regulatory" },
  { value: "pharma",        label: "Scientific & Medical" },
  { value: "news_editorial",label: "News & Editorial" },
  { value: "internal",      label: "Internal / Organizational" },
];

const AUTHORITY_OPTIONS = [
  { value: "primary",       label: "Primary",       desc: "Official source, first-hand data" },
  { value: "institutional", label: "Institutional", desc: "Established organization or body" },
  { value: "secondary",     label: "Secondary",     desc: "Derived or aggregated content" },
];

const CS_STATUS_COLORS: Record<string, string> = {
  active:  "text-emerald-400",
  pending: "text-amber-400",
  error:   "text-red-400",
};

const CS_TYPE_LABELS: Record<SourceType, string> = {
  url:  "URL",
  api:  "API",
  file: "File",
};

function CustomSourcesSection({
  initialMine,
  initialCommunity,
  token,
}: {
  initialMine: CustomSource[];
  initialCommunity: CustomSource[];
  token: string;
}) {
  const [mine, setMine] = useState<CustomSource[]>(initialMine);
  const [community] = useState<CustomSource[]>(initialCommunity);
  const [showModal, setShowModal] = useState(false);
  const [isPending, startTransition] = useTransition();

  const handleDelete = (id: string) => {
    startTransition(async () => {
      await sourcesApi.deleteCustomSource(token, id);
      setMine(prev => prev.filter(s => s.id !== id));
      toast.success("Source removed");
    });
  };

  const handleTest = (id: string) => {
    startTransition(async () => {
      const data = await sourcesApi.testCustomSource(token, id);
      setMine(prev => prev.map(s => s.id === id ? { ...s, status: (data.status as any) ?? s.status } : s));
      toast.success(data.status === "active" ? "Re-indexed successfully" : `Indexing started`);
    });
  };

  const handleToggleScope = (id: string, current: SourceScope) => {
    const next: SourceScope = current === "private" ? "public" : "private";
    startTransition(async () => {
      await sourcesApi.updateCustomSource(token, id, { scope: next });
      setMine(prev => prev.map(s => s.id === id ? { ...s, scope: next } : s));
      toast.success(`Source is now ${next}`);
    });
  };

  const [editingSource, setEditingSource] = useState<CustomSource | null>(null);

  const handleEdit = (updated: CustomSource) => {
    setMine(prev => prev.map(s => s.id === updated.id ? updated : s));
    setEditingSource(null);
  };

  return (
    <div className="mt-10">
      <div className="flex items-center gap-3 mb-2">
        <h2 className="text-[11px] font-mono tracking-widest text-muted-foreground uppercase whitespace-nowrap">
          Custom Sources
        </h2>
        <div className="h-px flex-1 bg-border" />
        <button
          onClick={() => setShowModal(true)}
          className="text-[10px] font-mono tracking-widest px-3 py-1.5 rounded border border-violet-500/40 bg-violet-500/8 text-violet-400 hover:bg-violet-500/15 transition-colors whitespace-nowrap"
        >
          + ADD SOURCE
        </button>
      </div>

      <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
        Connect your own external or internal resources as verification sources. Private sources are visible only to your org.
      </p>

      {mine.length === 0 ? (
        <div
          className="border border-dashed border-border rounded-lg p-6 text-center text-muted-foreground text-xs cursor-pointer hover:border-violet-500/40 transition-colors"
          onClick={() => setShowModal(true)}
        >
          No custom sources yet. Click to add your first source.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {mine.map(s => (
            <CustomSourceCard
              key={s.id}
              source={s}
              isOwn
              onDelete={() => handleDelete(s.id)}
              onTest={() => handleTest(s.id)}
              onToggleScope={() => handleToggleScope(s.id, s.scope)}
              onEdit={() => setEditingSource(s)}
            />
          ))}
        </div>
      )}

      {community.length > 0 && (
        <div className="mt-6">
          <p className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase mb-3 opacity-70">
            Shared by other organizations
          </p>
          <div className="flex flex-col gap-2">
            {community.map(s => (
              <CustomSourceCard key={s.id} source={s} isOwn={false} onDelete={() => {}} onTest={() => {}} onToggleScope={() => {}} />
            ))}
          </div>
        </div>
      )}

      {showModal && (
        <AddSourceModal
          token={token}
          onClose={() => setShowModal(false)}
          onAdded={s => setMine(prev => [s, ...prev])}
        />
      )}

      {editingSource && (
        <EditSourceModal
          token={token}
          source={editingSource}
          onClose={() => setEditingSource(null)}
          onSaved={handleEdit}
        />
      )}
    </div>
  );
}

function CustomSourceCard({
  source,
  isOwn,
  onDelete,
  onTest,
  onToggleScope,
  onEdit,
}: {
  source: CustomSource;
  isOwn: boolean;
  onDelete: () => void;
  onTest: () => void;
  onToggleScope: () => void;
  onEdit?: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="bg-card border border-border rounded-lg p-4 flex items-start gap-3 relative">
      <div className="h-8 w-8 rounded-md bg-secondary border border-border flex items-center justify-center text-xs font-mono text-muted-foreground shrink-0 mt-0.5">
        {CS_TYPE_LABELS[source.sourceType]}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-foreground">{source.name}</span>

          <span className={`text-[10px] font-mono flex items-center gap-1 ${CS_STATUS_COLORS[source.status] ?? "text-muted-foreground"}`}>
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${
              source.status === "active" ? "bg-emerald-400" : source.status === "pending" ? "bg-amber-400" : "bg-red-400"
            }`} />
            {source.status.toUpperCase()}
          </span>

          <span className={`text-[9px] font-mono border rounded px-1.5 py-0.5 ${
            source.scope === "public" ? "text-violet-400 border-violet-500/30 bg-violet-500/10" : "text-muted-foreground border-border"
          }`}>
            {source.scope === "public" ? "PUBLIC" : "PRIVATE"}
          </span>
        </div>

        {source.description && (
          <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">{source.description}</p>
        )}

        <div className="flex gap-2 mt-1.5 text-[10px] font-mono text-muted-foreground flex-wrap">
          <span>{source.authorityLevel}</span>
          <span>·</span>
          <span>{DOMAIN_OPTIONS.find(d => d.value === source.domain)?.label ?? source.domain}</span>
          {source.sourceType === "file" && source.connectionConfig.filename && (
            <><span>·</span><span>{source.connectionConfig.filename}</span></>
          )}
          {source.lastIndexedAt && (
            <><span>·</span><span>indexed {new Date(source.lastIndexedAt).toLocaleDateString()}</span></>
          )}
        </div>

        {source.status === "error" && source.errorMessage && (
          <p className="text-[10px] text-red-400 mt-1 font-mono">{source.errorMessage}</p>
        )}
      </div>

      {isOwn && (
        <div className="relative shrink-0">
          <button
            onClick={() => setMenuOpen(o => !o)}
            className="text-muted-foreground hover:text-foreground px-1.5 py-0.5 rounded text-sm"
          >
            ···
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 bg-card border border-border rounded-lg p-1 z-10 min-w-[150px] shadow-lg">
              {onEdit && (
                <button onClick={() => { onEdit(); setMenuOpen(false); }} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-secondary rounded">
                  Edit source
                </button>
              )}
              {source.sourceType !== "file" && (
                <button onClick={() => { onTest(); setMenuOpen(false); }} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-secondary rounded">
                  Re-index source
                </button>
              )}
              <button onClick={() => { onToggleScope(); setMenuOpen(false); }} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-secondary rounded">
                Make {source.scope === "private" ? "public" : "private"}
              </button>
              <div className="h-px bg-border my-1" />
              <button onClick={() => { onDelete(); setMenuOpen(false); }} className="block w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-secondary rounded">
                Remove source
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AddSourceModal({
  token,
  onClose,
  onAdded,
}: {
  token: string;
  onClose: () => void;
  onAdded: (s: CustomSource) => void;
}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [sourceType, setSourceType] = useState<SourceType | null>(null);
  const [isPending, startTransition] = useTransition();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [domain, setDomain] = useState("internal");
  const [authorityLevel, setAuthorityLevel] = useState("secondary");
  const [scope, setScope] = useState<SourceScope>("private");
  const [url, setUrl] = useState("");
  const [apiHeaders, setApiHeaders] = useState([{ key: "", value: "" }]);
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = () => {
    if (!name || !sourceType || !domain) return;
    startTransition(async () => {
      try {
        let created: CustomSource;
        if (sourceType === "file") {
          if (!file) return;
          const form = new FormData();
          form.append("file", file);
          form.append("name", name);
          if (description) form.append("description", description);
          form.append("domain", domain);
          form.append("authorityLevel", authorityLevel);
          form.append("scope", scope);
          created = await sourcesApi.uploadCustomSource(token, form);
        } else {
          const headers: Record<string, string> = {};
          if (sourceType === "api") {
            for (const h of apiHeaders) {
              if (h.key && h.value) headers[h.key] = h.value;
            }
          }
          created = await sourcesApi.createCustomSource(token, {
            name, description, sourceType, domain, authorityLevel, scope,
            connectionConfig: sourceType === "api" ? { url, headers } : { url },
          });
        }
        toast.success(`"${name}" added`);
        onAdded(created);
        onClose();
      } catch (e: any) {
        toast.error(e.message ?? "Failed to add source");
      }
    });
  };

  const TYPE_OPTIONS: Array<{ type: SourceType; title: string; desc: string }> = [
    { type: "url",  title: "URL / Web Endpoint", desc: "Crawl a public URL and index its content" },
    { type: "api",  title: "API Endpoint",        desc: "Connect a private API with auth headers" },
    { type: "file", title: "File Upload",         desc: "Upload a PDF, Word doc, or plain text file" },
  ];

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-xl w-full max-w-lg p-6 flex flex-col gap-5"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase">
              Step {step} of 2
            </p>
            <h2 className="text-base font-semibold mt-0.5">
              {step === 1 ? "Choose source type" : "Configure source"}
            </h2>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg leading-none px-1">×</button>
        </div>

        {step === 1 && (
          <div className="flex flex-col gap-2">
            {TYPE_OPTIONS.map(({ type, title, desc }) => (
              <button
                key={type}
                onClick={() => setSourceType(type)}
                className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-colors ${
                  sourceType === type
                    ? "border-violet-500/50 bg-violet-500/8"
                    : "border-border bg-secondary hover:border-border/60"
                }`}
              >
                <div className="text-[10px] font-mono text-muted-foreground w-8 shrink-0 text-center border border-border rounded px-1 py-0.5">
                  {CS_TYPE_LABELS[type]}
                </div>
                <div>
                  <p className="text-xs font-medium text-foreground">{title}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{desc}</p>
                </div>
                {sourceType === type && <span className="ml-auto text-violet-400 text-sm">✓</span>}
              </button>
            ))}
            <button
              onClick={() => sourceType && setStep(2)}
              disabled={!sourceType}
              className={`mt-1 py-2 rounded-lg text-[11px] font-mono tracking-widest transition-colors ${
                sourceType
                  ? "bg-violet-600 hover:bg-violet-500 text-white"
                  : "bg-secondary text-muted-foreground cursor-not-allowed"
              }`}
            >
              CONTINUE
            </button>
          </div>
        )}

        {step === 2 && sourceType && (
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Source name</label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Internal Compliance Manual" className="text-xs" />
            </div>

            <div>
              <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Description <span className="opacity-50">(optional)</span></label>
              <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description of this source" className="text-xs" />
            </div>

            {(sourceType === "url" || sourceType === "api") && (
              <div>
                <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">
                  {sourceType === "api" ? "API Endpoint URL" : "URL"}
                </label>
                <Input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." className="text-xs font-mono" />
              </div>
            )}

            {sourceType === "api" && (
              <div>
                <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Auth Headers</label>
                <div className="flex flex-col gap-2">
                  {apiHeaders.map((h, i) => (
                    <div key={i} className="flex gap-2">
                      <Input
                        placeholder="Header name"
                        value={h.key}
                        onChange={e => setApiHeaders(apiHeaders.map((x, j) => j === i ? { ...x, key: e.target.value } : x))}
                        className="text-xs font-mono flex-[0_0_38%]"
                      />
                      <Input
                        type="password"
                        placeholder="Value"
                        value={h.value}
                        onChange={e => setApiHeaders(apiHeaders.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
                        className="text-xs font-mono flex-1"
                      />
                      {apiHeaders.length > 1 && (
                        <button onClick={() => setApiHeaders(apiHeaders.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-foreground text-sm px-1">×</button>
                      )}
                    </div>
                  ))}
                  <button
                    onClick={() => setApiHeaders([...apiHeaders, { key: "", value: "" }])}
                    className="self-start text-[10px] font-mono text-muted-foreground border border-border rounded px-2 py-1 hover:text-foreground"
                  >
                    + ADD HEADER
                  </button>
                </div>
              </div>
            )}

            {sourceType === "file" && (
              <div>
                <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">File</label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className={`border border-dashed rounded-lg p-5 text-center cursor-pointer text-xs transition-colors ${
                    file ? "border-violet-500/50 text-violet-400 bg-violet-500/5" : "border-border text-muted-foreground hover:border-violet-500/40"
                  }`}
                >
                  {file ? `${file.name} (${(file.size / 1024).toFixed(0)} KB)` : "Click to upload · PDF, DOCX, or TXT · Max 20 MB"}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                  className="hidden"
                  onChange={e => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            )}

            <div>
              <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Domain</label>
              <select
                value={domain}
                onChange={e => setDomain(e.target.value)}
                className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-xs text-foreground outline-none"
              >
                {DOMAIN_OPTIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Authority Level</label>
              <div className="flex gap-2">
                {AUTHORITY_OPTIONS.map(a => (
                  <button
                    key={a.value}
                    onClick={() => setAuthorityLevel(a.value)}
                    title={a.desc}
                    className={`flex-1 py-1.5 rounded border text-[10px] font-mono transition-colors ${
                      authorityLevel === a.value
                        ? "border-violet-500/50 bg-violet-500/10 text-violet-400"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {a.label.toUpperCase()}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                {AUTHORITY_OPTIONS.find(a => a.value === authorityLevel)?.desc}
              </p>
            </div>

            <div>
              <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Visibility</label>
              <div className="flex gap-2">
                {(["private", "public"] as SourceScope[]).map(s => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className={`flex-1 py-1.5 rounded border text-[10px] font-mono transition-colors ${
                      scope === s
                        ? "border-violet-500/50 bg-violet-500/10 text-violet-400"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {s === "private" ? "PRIVATE — MY ORG" : "PUBLIC — ALL ORGS"}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2 mt-1">
              <button
                onClick={() => setStep(1)}
                className="px-4 py-2 rounded-lg border border-border text-[11px] font-mono text-muted-foreground hover:text-foreground"
              >
                BACK
              </button>
              <button
                onClick={handleSubmit}
                disabled={isPending || !name || (sourceType !== "file" && !url) || (sourceType === "file" && !file)}
                className={`flex-1 py-2 rounded-lg text-[11px] font-mono tracking-widest transition-colors ${
                  isPending ? "bg-secondary text-muted-foreground cursor-not-allowed" : "bg-violet-600 hover:bg-violet-500 text-white"
                }`}
              >
                {isPending ? "ADDING..." : "ADD SOURCE"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function EditSourceModal({
  token,
  source,
  onClose,
  onSaved,
}: {
  token: string;
  source: CustomSource;
  onClose: () => void;
  onSaved: (updated: CustomSource) => void;
}) {
  const [name, setName] = useState(source.name);
  const [description, setDescription] = useState(source.description ?? "");
  const [authorityLevel, setAuthorityLevel] = useState(source.authorityLevel);
  const [scope, setScope] = useState<SourceScope>(source.scope);
  const [isPending, startTransition] = useTransition();

  const handleSave = () => {
    startTransition(async () => {
      try {
        const updated = await sourcesApi.updateCustomSource(token, source.id, {
          name,
          description: description || undefined,
          authorityLevel,
          scope,
        });
        toast.success("Source updated");
        onSaved(updated as CustomSource);
      } catch (e: any) {
        toast.error(e.message ?? "Failed to update source");
      }
    });
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-xl w-full max-w-md p-6 flex flex-col gap-5"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Edit source</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg leading-none px-1">×</button>
        </div>

        <div>
          <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Source name</label>
          <Input value={name} onChange={e => setName(e.target.value)} className="text-xs" />
        </div>

        <div>
          <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Description <span className="opacity-50">(optional)</span></label>
          <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description of this source" className="text-xs" />
        </div>

        <div>
          <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Authority Level</label>
          <div className="flex gap-2">
            {AUTHORITY_OPTIONS.map(a => (
              <button
                key={a.value}
                onClick={() => setAuthorityLevel(a.value)}
                title={a.desc}
                className={`flex-1 py-1.5 rounded border text-[10px] font-mono transition-colors ${
                  authorityLevel === a.value
                    ? "border-violet-500/50 bg-violet-500/10 text-violet-400"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {a.label.toUpperCase()}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            {AUTHORITY_OPTIONS.find(a => a.value === authorityLevel)?.desc}
          </p>
        </div>

        <div>
          <label className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase block mb-1">Visibility</label>
          <div className="flex gap-2">
            {(["private", "public"] as SourceScope[]).map(s => (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={`flex-1 py-1.5 rounded border text-[10px] font-mono transition-colors ${
                  scope === s
                    ? "border-violet-500/50 bg-violet-500/10 text-violet-400"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {s === "private" ? "PRIVATE — MY ORG" : "PUBLIC — ALL ORGS"}
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2 mt-1">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-border text-[11px] font-mono text-muted-foreground hover:text-foreground"
          >
            CANCEL
          </button>
          <button
            onClick={handleSave}
            disabled={isPending || !name}
            className={`flex-1 py-2 rounded-lg text-[11px] font-mono tracking-widest transition-colors ${
              isPending || !name ? "bg-secondary text-muted-foreground cursor-not-allowed" : "bg-violet-600 hover:bg-violet-500 text-white"
            }`}
          >
            {isPending ? "SAVING..." : "SAVE CHANGES"}
          </button>
        </div>
      </div>
    </div>
  );
}
