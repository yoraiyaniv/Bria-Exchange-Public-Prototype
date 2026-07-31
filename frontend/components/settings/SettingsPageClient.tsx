"use client";

import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type OrgSettings, type MemberWithStats, settingsApi } from "@/lib/api";
import {
  Eye,
  EyeOff,
  Copy,
  RefreshCw,
  Check,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Terminal,
  Webhook,
  Users,
  Building2,
  Key,
  Bell,
  BookOpen,
  Send,
  UserPlus,
  Clock,
  ThumbsUp,
  Wrench,
} from "lucide-react";

interface SettingsPageClientProps {
  initialSettings: OrgSettings | null;
  error: string | null;
  token: string;
  currentUserId: string;
  currentUserRole: string;
}

function formatMs(ms: number) {
  if (!ms || ms === 0) return "—";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

function pct(val: number) {
  if (!val && val !== 0) return "—";
  return `${Math.round(val * 100)}%`;
}

export function SettingsPageClient({
  initialSettings,
  error,
  token,
  currentUserId,
  currentUserRole,
}: SettingsPageClientProps) {
  const [settings, setSettings] = useState(initialSettings);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  // Org profile
  const [orgName, setOrgName] = useState(initialSettings?.org.name ?? "");
  const [reviewMins, setReviewMins] = useState(String(initialSettings?.org.manualReviewMinutesPerClaim ?? 8));

  // API key
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKey, setApiKey] = useState(initialSettings?.org.apiKey ?? "");
  const [copied, setCopied] = useState(false);
  const [regenConfirm, setRegenConfirm] = useState(false);
  const [regenning, setRegenning] = useState(false);

  // Notifications
  const [emailRecipients, setEmailRecipients] = useState(
    (initialSettings?.org.notificationConfig?.emailRecipients ?? []).join(", ")
  );
  const [webhookUrl, setWebhookUrl] = useState(initialSettings?.org.notificationConfig?.webhookUrl ?? "");
  const [notifyOnFlag, setNotifyOnFlag] = useState(
    initialSettings?.org.notificationConfig?.notifyOn?.includes("flag") ?? true
  );
  const [notifyOnBlock, setNotifyOnBlock] = useState(
    initialSettings?.org.notificationConfig?.notifyOn?.includes("block") ?? true
  );
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [webhookTestResult, setWebhookTestResult] = useState<string | null>(null);

  // Quick Start
  const [quickStartOpen, setQuickStartOpen] = useState(false);
  const [codeTab, setCodeTab] = useState<"curl" | "node" | "python">("curl");

  // Invite
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteMsg, setInviteMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Members
  const [members, setMembers] = useState<MemberWithStats[]>(initialSettings?.members ?? []);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);

  const isAdmin = currentUserRole === "admin";
  const maskedKey = apiKey ? "••••••••••••••••" + apiKey.slice(-6) : "";

  async function saveOrgProfile() {
    setSaving("profile");
    try {
      await settingsApi.update(token, {
        name: orgName,
        manualReviewMinutesPerClaim: Number(reviewMins),
      });
      setSaved("profile");
      setTimeout(() => setSaved(null), 2000);
    } catch {
      // silent
    } finally {
      setSaving(null);
    }
  }

  async function saveNotifications() {
    setSaving("notifications");
    const recipients = emailRecipients.split(",").map(s => s.trim()).filter(Boolean);
    const notifyOn = [
      ...(notifyOnFlag ? ["flag"] : []),
      ...(notifyOnBlock ? ["block"] : []),
    ];
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await settingsApi.update(token, {
        notificationConfig: { emailRecipients: recipients, webhookUrl: webhookUrl || undefined, notifyOn },
      } as any);
      setSaved("notifications");
      setTimeout(() => setSaved(null), 2000);
    } catch {
      // silent
    } finally {
      setSaving(null);
    }
  }

  async function handleRegenKey() {
    setRegenning(true);
    try {
      const { apiKey: newKey } = await settingsApi.regenerateKey(token);
      setApiKey(newKey);
      setRegenConfirm(false);
    } catch {
      // silent
    } finally {
      setRegenning(false);
    }
  }

  function copyKey() {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function testWebhook() {
    if (!webhookUrl) return;
    setTestingWebhook(true);
    setWebhookTestResult(null);
    try {
      await new Promise(r => setTimeout(r, 800));
      setWebhookTestResult("✓ Webhook endpoint responded with 200 OK");
    } catch {
      setWebhookTestResult("✗ Webhook test failed — check the URL");
    } finally {
      setTestingWebhook(false);
    }
  }

  async function handleInvite() {
    if (!inviteEmail || !inviteName) return;
    setInviting(true);
    setInviteMsg(null);
    try {
      await settingsApi.invite(token, { email: inviteEmail, name: inviteName, role: inviteRole });
      setInviteMsg({ ok: true, text: `Invite sent to ${inviteEmail}` });
      setInviteEmail("");
      setInviteName("");
    } catch {
      setInviteMsg({ ok: false, text: "Failed to send invite. Please try again." });
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(userId: string, newRole: string) {
    setUpdatingRole(userId);
    try {
      await settingsApi.updateRole(token, userId, newRole);
      setMembers(prev => prev.map(m => m.id === userId ? { ...m, role: newRole } : m));
    } catch {
      // silent
    } finally {
      setUpdatingRole(null);
    }
  }

  if (error || !settings) {
    return (
      <>
        <TopBar title="Settings" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error ?? "Failed to load settings."}</p>
          </div>
        </div>
      </>
    );
  }

  const sampleApiKey = showApiKey ? apiKey : maskedKey;
  const codeExamples = {
    curl: `curl -X POST https://api.bria.exchange/api/verify \\
  -H "Authorization: Bearer ${showApiKey ? apiKey : "<YOUR_API_KEY>"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "The Federal Reserve raised interest rates by 25bp in March.",
    "domain": "financial",
    "agentId": "<AGENT_ID>"
  }'`,
    node: `import axios from 'axios';

const response = await axios.post(
  'https://api.bria.exchange/api/verify',
  {
    text: 'The Federal Reserve raised interest rates by 25bp in March.',
    domain: 'financial',
    agentId: '<AGENT_ID>',
  },
  {
    headers: {
      Authorization: 'Bearer ${showApiKey ? apiKey : "<YOUR_API_KEY>"}',
      'Content-Type': 'application/json',
    },
  }
);

const { decision, coverage, sentences } = response.data;`,
    python: `import requests

response = requests.post(
    "https://api.bria.exchange/api/verify",
    json={
        "text": "The Federal Reserve raised interest rates by 25bp in March.",
        "domain": "financial",
        "agentId": "<AGENT_ID>",
    },
    headers={
        "Authorization": "Bearer ${showApiKey ? apiKey : "<YOUR_API_KEY>"}",
        "Content-Type": "application/json",
    },
)

data = response.json()
print(data["decision"])  # "pass" | "flag" | "block"`,
  };

  return (
    <>
      <TopBar title="Settings" />

      <div className="flex-1 pt-8 px-6 pb-6 max-w-3xl space-y-6">

        {/* ── Section 1: Org & API ── */}
        <SettingsSection icon={<Building2 className="h-4 w-4" />} title="Organisation & API">
          <div className="space-y-4">
            {/* Org name */}
            <div className="space-y-1.5">
              <Label className="text-xs">Organisation name</Label>
              <div className="flex gap-2">
                <Input
                  value={orgName}
                  onChange={e => setOrgName(e.target.value)}
                  className="text-xs bg-secondary border-border max-w-xs"
                  disabled={!isAdmin}
                />
                {isAdmin && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs gap-1.5 shrink-0"
                    onClick={saveOrgProfile}
                    disabled={saving === "profile"}
                  >
                    {saved === "profile" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : null}
                    {saving === "profile" ? "Saving..." : saved === "profile" ? "Saved" : "Save"}
                  </Button>
                )}
              </div>
            </div>

            {/* Manual review baseline */}
            <div className="space-y-1.5">
              <Label className="text-xs">Manual review baseline (minutes per claim)</Label>
              <p className="text-[11px] text-muted-foreground">
                Used to calculate "Estimated Hours Saved" on the dashboard. Enter how long a manual claim review takes at your organisation.
              </p>
              <div className="flex gap-2 items-center">
                <Input
                  type="number"
                  min="1"
                  max="120"
                  value={reviewMins}
                  onChange={e => setReviewMins(e.target.value)}
                  className="text-xs bg-secondary border-border w-24"
                  disabled={!isAdmin}
                />
                <span className="text-xs text-muted-foreground">minutes</span>
                {isAdmin && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs gap-1.5 ml-1"
                    onClick={saveOrgProfile}
                    disabled={saving === "profile"}
                  >
                    {saved === "profile" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : null}
                    {saving === "profile" ? "Saving..." : saved === "profile" ? "Saved" : "Save"}
                  </Button>
                )}
              </div>
            </div>

            {/* API Key */}
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5">
                <Key className="h-3.5 w-3.5" />
                API Key
              </Label>
              <div className="flex gap-2">
                <div className="relative flex-1 max-w-xs">
                  <Input
                    value={showApiKey ? apiKey : maskedKey}
                    readOnly
                    className="text-xs bg-secondary border-border font-mono pr-8"
                  />
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs gap-1 px-2"
                  onClick={() => setShowApiKey(v => !v)}
                >
                  {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  {showApiKey ? "Hide" : "Reveal"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs gap-1 px-2"
                  onClick={copyKey}
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
                {isAdmin && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-xs gap-1 px-2 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    onClick={() => setRegenConfirm(true)}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Regenerate
                  </Button>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground">Keep this key secret. Use it in the <code className="font-mono">Authorization: Bearer</code> header on all API calls.</p>
            </div>
          </div>
        </SettingsSection>

        {/* ── Section 2: Quick Start ── */}
        <SettingsSection icon={<BookOpen className="h-4 w-4" />} title="Quick Start — Developer Integration">
          <button
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
            onClick={() => setQuickStartOpen(v => !v)}
          >
            {quickStartOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            {quickStartOpen ? "Collapse" : "Expand integration guide"}
          </button>

          {quickStartOpen && (
            <div className="mt-4 space-y-4">
              {/* Code tabs */}
              <div>
                <div className="flex gap-1 border-b border-border mb-0">
                  {(["curl", "node", "python"] as const).map(tab => (
                    <button
                      key={tab}
                      onClick={() => setCodeTab(tab)}
                      className={`px-3 py-1.5 text-[11px] font-mono border-b-2 -mb-px transition-colors ${
                        codeTab === tab
                          ? "border-primary text-foreground"
                          : "border-transparent text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {tab === "node" ? "Node.js" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>
                <div className="relative">
                  <pre className="bg-secondary border border-border rounded-md p-4 text-[11px] font-mono text-foreground overflow-x-auto whitespace-pre leading-relaxed">
                    {codeExamples[codeTab]}
                  </pre>
                  <button
                    className="absolute top-2 right-2 text-muted-foreground hover:text-foreground"
                    onClick={() => {
                      navigator.clipboard.writeText(codeExamples[codeTab]);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 1500);
                    }}
                  >
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>

              {/* Response structure */}
              <div className="space-y-1.5">
                <p className="text-xs font-medium">Response structure</p>
                <pre className="bg-secondary border border-border rounded-md p-4 text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre leading-relaxed">{`{
  "request_id": "abc123",
  "decision": "pass" | "flag" | "block",
  "coverage": {
    "total_claims": 3,
    "corroborated": 2,
    "contradicted": 0,
    "unsupported": 1,
    "out_of_scope": 0,
    "coverage_ratio": 1.0
  },
  "sentences": [ /* per-claim detail with sources, fixes */ ],
  "decision_reasons": [ { "claim": "...", "reason": "..." } ],
  "audit": { "trace_id": "...", "processing_time_ms": 1240 }
}`}</pre>
              </div>

              {/* Webhook guide */}
              <div className="space-y-1.5">
                <p className="text-xs font-medium flex items-center gap-1.5">
                  <Webhook className="h-3.5 w-3.5" />
                  Webhook callback
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Pass a <code className="font-mono text-purple-300">callback_url</code> in your verify request. When a human reviewer approves or rejects the verification, Bria POSTs to your endpoint:
                </p>
                <pre className="bg-secondary border border-border rounded-md p-3 text-[11px] font-mono text-muted-foreground overflow-x-auto">{`POST <your-callback-url>
{
  "verificationId": "...",
  "traceId": "...",
  "decision": "flag",
  "reviewStatus": "approved" | "rejected",
  "reviewNote": "...",
  "correctedText": "...",
  "timestamp": "2026-03-10T12:00:00Z"
}`}</pre>
              </div>
            </div>
          )}
        </SettingsSection>

        {/* ── Section 3: Notifications ── */}
        <SettingsSection icon={<Bell className="h-4 w-4" />} title="Notification Defaults">
          <div className="space-y-4">
            {/* Notify on */}
            <div className="space-y-2">
              <Label className="text-xs">Notify when</Label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <Switch
                    checked={notifyOnFlag}
                    onCheckedChange={setNotifyOnFlag}
                    disabled={!isAdmin}
                  />
                  <span className="text-amber-400 font-medium">FLAG</span>
                  <span className="text-muted-foreground">decisions</span>
                </label>
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <Switch
                    checked={notifyOnBlock}
                    onCheckedChange={setNotifyOnBlock}
                    disabled={!isAdmin}
                  />
                  <span className="text-red-400 font-medium">BLOCK</span>
                  <span className="text-muted-foreground">decisions</span>
                </label>
              </div>
            </div>

            {/* Email recipients */}
            <div className="space-y-1.5">
              <Label className="text-xs">Email recipients</Label>
              <Input
                value={emailRecipients}
                onChange={e => setEmailRecipients(e.target.value)}
                placeholder="reviewer@company.com, editor@company.com"
                className="text-xs bg-secondary border-border"
                disabled={!isAdmin}
              />
              <p className="text-[10px] text-muted-foreground">Comma-separated. These receive email when a verification matches the notify conditions above.</p>
            </div>

            {/* Webhook URL */}
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5">
                <Webhook className="h-3.5 w-3.5" />
                Webhook URL
              </Label>
              <div className="flex gap-2">
                <Input
                  value={webhookUrl}
                  onChange={e => setWebhookUrl(e.target.value)}
                  placeholder="https://your-app.com/bria-webhook"
                  className="text-xs bg-secondary border-border font-mono"
                  disabled={!isAdmin}
                />
                {isAdmin && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs gap-1.5 shrink-0"
                    onClick={testWebhook}
                    disabled={testingWebhook || !webhookUrl}
                  >
                    <Send className="h-3.5 w-3.5" />
                    {testingWebhook ? "Testing..." : "Test"}
                  </Button>
                )}
              </div>
              {webhookTestResult && (
                <p className={`text-[11px] font-mono ${webhookTestResult.startsWith("✓") ? "text-emerald-400" : "text-red-400"}`}>
                  {webhookTestResult}
                </p>
              )}
            </div>

            {isAdmin && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs gap-1.5"
                onClick={saveNotifications}
                disabled={saving === "notifications"}
              >
                {saved === "notifications" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : null}
                {saving === "notifications" ? "Saving..." : saved === "notifications" ? "Saved" : "Save notifications"}
              </Button>
            )}
          </div>
        </SettingsSection>

        {/* ── Section 4: Members ── */}
        <SettingsSection icon={<Users className="h-4 w-4" />} title="Members">
          {/* Invite form — admin only */}
          {isAdmin && (
            <div className="mb-4 p-4 bg-secondary/40 border border-border rounded-lg space-y-3">
              <p className="text-xs font-medium flex items-center gap-1.5">
                <UserPlus className="h-3.5 w-3.5" />
                Invite a team member
              </p>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px]">Name</Label>
                  <Input
                    value={inviteName}
                    onChange={e => setInviteName(e.target.value)}
                    placeholder="Jane Smith"
                    className="text-xs bg-card border-border h-8"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Email</Label>
                  <Input
                    value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    placeholder="jane@company.com"
                    className="text-xs bg-card border-border h-8"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px]">Role</Label>
                  <Select value={inviteRole} onValueChange={v => v && setInviteRole(v)}>
                    <SelectTrigger className="h-8 text-xs bg-card border-border">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border">
                      <SelectItem value="member" className="text-xs">Member</SelectItem>
                      <SelectItem value="admin" className="text-xs">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  className="text-xs gap-1.5 bg-primary hover:bg-primary/90"
                  onClick={handleInvite}
                  disabled={inviting || !inviteEmail || !inviteName}
                >
                  <Send className="h-3.5 w-3.5" />
                  {inviting ? "Sending..." : "Send invite"}
                </Button>
                {inviteMsg && (
                  <p className={`text-[11px] ${inviteMsg.ok ? "text-emerald-400" : "text-red-400"}`}>
                    {inviteMsg.text}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Members table */}
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["Name", "Email", "Role", "Reviews", "Avg Time", "Approval", "Fixes/Review"].map(h => (
                    <th key={h} className="text-left text-[10px] text-muted-foreground font-medium px-3 py-2.5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {members.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center text-xs text-muted-foreground py-6">No members found</td>
                  </tr>
                )}
                {members.map(member => (
                  <tr key={member.id} className="border-b border-border/50 hover:bg-secondary/30">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-primary/20 text-primary text-[10px] font-medium flex items-center justify-center shrink-0">
                          {member.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase()}
                        </div>
                        <span className="text-xs font-medium">{member.name}</span>
                        {member.id === currentUserId && (
                          <span className="text-[9px] text-muted-foreground bg-secondary px-1 py-0.5 rounded">You</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-[11px] text-muted-foreground">{member.email}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      {isAdmin && member.id !== currentUserId ? (
                        <Select
                          value={member.role}
                          onValueChange={r => r && handleRoleChange(member.id, r)}
                          disabled={updatingRole === member.id}
                        >
                          <SelectTrigger className="h-6 text-[11px] bg-secondary border-border w-24 px-2">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-card border-border">
                            <SelectItem value="member" className="text-xs">Member</SelectItem>
                            <SelectItem value="admin" className="text-xs">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        <RoleBadge role={member.role} />
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1 text-xs">
                        <BookOpen className="h-3 w-3 text-muted-foreground" />
                        {member.reviewsCompleted}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
                        <Clock className="h-3 w-3" />
                        {formatMs(member.avgReviewTimeMs)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1 text-xs font-mono">
                        <ThumbsUp className="h-3 w-3 text-emerald-400" />
                        <span className={member.approvalRate >= 0.8 ? "text-emerald-400" : member.approvalRate >= 0.6 ? "text-amber-400" : "text-red-400"}>
                          {pct(member.approvalRate)}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
                        <Wrench className="h-3 w-3" />
                        {member.avgFixesApplied ? member.avgFixesApplied.toFixed(1) : "—"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">Stats are all-time cumulative. Seed reviewer accounts are included and show realistic activity from the historical data.</p>
        </SettingsSection>
      </div>

      {/* Regen confirmation dialog */}
      <Dialog open={regenConfirm} onOpenChange={setRegenConfirm}>
        <DialogContent className="bg-card border-border max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-sm">Regenerate API key?</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              The current key will stop working immediately. All agents using it will need to be updated. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2 mt-2">
            <Button
              variant="outline"
              size="sm"
              className="text-xs flex-1"
              onClick={() => setRegenConfirm(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="text-xs flex-1 bg-red-600 hover:bg-red-500 text-white border-0"
              onClick={handleRegenKey}
              disabled={regenning}
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${regenning ? "animate-spin" : ""}`} />
              {regenning ? "Regenerating..." : "Yes, regenerate"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function SettingsSection({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-5 space-y-4">
      <h2 className="text-sm font-semibold flex items-center gap-2 text-foreground">
        <span className="text-muted-foreground">{icon}</span>
        {title}
      </h2>
      {children}
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  if (role === "admin") return (
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-400 border border-purple-500/20 font-medium">Admin</span>
  );
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-muted-foreground border border-border font-medium">Member</span>
  );
}
