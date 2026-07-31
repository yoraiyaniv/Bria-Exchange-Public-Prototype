"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import InputArea from "@/components/InputArea";
import ProcessingView from "@/components/ProcessingView";
import ResultView from "@/components/ResultView";
import UsageMeter from "@/components/UsageMeter";
import { verifyStream } from "@/lib/api";
import type { VerifyResponse, PreviewClaim, VerifiedClaim } from "@/lib/api";
import UserMenu from "@/components/UserMenu";

const SAMPLES: Array<{ label: string; text: string }> = [
  {
    label: "Company facts",
    text: "Tesla was incorporated in 2003 by Martin Eberhard and Marc Tarpenning. Apple carried out a 4-for-1 stock split in August 2020. Nvidia is headquartered in Santa Clara, California and operates in the semiconductor industry.",
  },
  {
    label: "Economic data",
    text: "The US unemployment rate surged to 14.7% in April 2020 during the COVID-19 pandemic. US GDP per capita was approximately $76,000 in 2023. Japan's population was about 125 million in 2022.",
  },
  {
    label: "Health & science",
    text: "The World Health Organization declared COVID-19 a pandemic on March 11, 2020. The first mRNA vaccines received emergency use authorization in December 2020. Semaglutide was originally developed as a treatment for type 2 diabetes before being approved for weight management.",
  },
];

type ViewState = "landing" | "processing" | "result";

function friendlyError(msg: string): string {
  const lower = msg.toLowerCase();
  if (lower.includes("422") || lower.includes("could not reach") || lower.includes("only access part"))
    return "We couldn\u2019t fetch that page. Try pasting the text directly instead.";
  if (lower.includes("too_long") || lower.includes("word limit"))
    return "That text is too long. Try a shorter passage (under 300 words).";
  if (lower.includes("rate_limit") || lower.includes("too many requests"))
    return "You\u2019re sending requests too quickly. Wait a moment and try again.";
  if (lower.includes("500") || lower.includes("verification failed"))
    return "Verification failed. The text may be too long or complex \u2014 try a shorter excerpt.";
  if (lower.includes("503") || lower.includes("unavailable"))
    return "The verification service is temporarily unavailable. Please try again shortly.";
  if (lower.includes("timeout"))
    return "Verification timed out. Try again with a shorter text.";
  return msg;
}

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [input, setInput] = useState("");
  const [view, setView] = useState<ViewState>("landing");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [limitError, setLimitError] = useState<{
    used: number;
    limit: number;
  } | null>(null);

  // Streaming state
  const [phase, setPhase] = useState("verifying");
  const [previewClaims, setPreviewClaims] = useState<PreviewClaim[]>([]);
  const [verifiedClaims, setVerifiedClaims] = useState<VerifiedClaim[]>([]);
  const [streamPublication, setStreamPublication] = useState<string | null>(
    null
  );

  // On mount: check if there's pending input from before auth redirect
  useEffect(() => {
    if (status !== "authenticated") return;
    const pending = sessionStorage.getItem("exchange_pending_input");
    if (pending) {
      sessionStorage.removeItem("exchange_pending_input");
      setInput(pending);
      // Auto-trigger verify after a tick so state is settled
      setTimeout(() => {
        setInput(pending);
        document.getElementById("auto-verify-trigger")?.click();
      }, 300);
    }
  }, [status]);

  const handleVerify = useCallback(async () => {
    if (!input.trim()) return;

    // Auth gate: if not logged in or no token, redirect to signup
    if (!session?.accessToken) {
      sessionStorage.setItem("exchange_pending_input", input.trim());
      router.push("/login");
      return;
    }

    setView("processing");
    setError(null);
    setLimitError(null);
    setResult(null);
    setPhase("verifying");
    setPreviewClaims([]);
    setVerifiedClaims([]);
    setStreamPublication(null);

    await verifyStream(
      input.trim(),
      {
        onStatus(statusPhase, detail) {
          setPhase(statusPhase);
          if (detail.publication) {
            setStreamPublication(detail.publication as string);
          }
        },
        onClaimsExtracted(claims) {
          setPreviewClaims(claims);
        },
        onClaimVerified(claim) {
          setVerifiedClaims((prev) => [...prev, claim]);
        },
        onResult(res) {
          setResult(res);
          setView("result");
        },
        onError(msg, detail) {
          if (detail.used !== undefined && detail.limit !== undefined) {
            setLimitError({
              used: detail.used as number,
              limit: detail.limit as number,
            });
            setError(null);
          } else {
            // Map raw error messages to user-friendly ones
            const friendly = friendlyError(msg);
            setError(friendly);
          }
          setView("landing");
        },
      },
      session.accessToken
    );
  }, [input, session, router]);

  function handleReset() {
    setView("landing");
    setInput("");
    setResult(null);
    setError(null);
    setLimitError(null);
    setPreviewClaims([]);
    setVerifiedClaims([]);
    setStreamPublication(null);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-[680px] space-y-8">
        <div className="flex items-center justify-between">
          <Logo />
          <UserMenu />
        </div>

        {view === "landing" && (
          <>
            <div className="space-y-2">
              <h1
                className="font-heading font-bold tracking-[-1.5px] leading-[1.1] text-text-primary"
                style={{
                  fontSize: "clamp(32px, 5vw, 48px)",
                }}
              >
                Paste any text. See what the sources say.
              </h1>
              <p className="font-body text-[15px] text-text-secondary">
                Claim-level verification against licensed sources.
                {!session && " Create a free account to get started."}
              </p>
            </div>

            <InputArea
              value={input}
              onChange={setInput}
              onVerify={handleVerify}
              loading={false}
            />

            {/* Hidden button for auto-trigger after auth redirect */}
            <button
              id="auto-verify-trigger"
              className="hidden"
              onClick={handleVerify}
            />

            {error && (
              <div className="flex items-start gap-3 card-elevated p-4">
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[#E8354A]/15 text-[10px] font-bold text-[#E8354A]">!</span>
                <div>
                  <p className="font-body text-sm text-text-primary">{error}</p>
                  <button
                    onClick={() => setError(null)}
                    className="mt-1 font-body text-xs text-text-muted hover:text-text-secondary"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {limitError && (
              <div className="rounded-lg border border-bria-purple/20 bg-bria-purple/10 p-3">
                <p className="font-body text-sm text-bria-purple-2">
                  Monthly limit reached ({limitError.used}/{limitError.limit}{" "}
                  claims). Upgrade to Pro for more.
                </p>
              </div>
            )}

            {session && <UsageMeter />}

            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((sample) => (
                <button
                  key={sample.label}
                  onClick={() => setInput(sample.text)}
                  className="rounded-full border border-border px-3 py-1.5 font-body text-xs font-semibold text-text-secondary transition-colors hover:border-bria-purple hover:text-bria-purple hover:bg-bria-purple/10"
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </>
        )}

        {view === "processing" && (
          <ProcessingView
            phase={phase}
            previewClaims={previewClaims}
            verifiedClaims={verifiedClaims}
            publication={streamPublication}
          />
        )}

        {view === "result" && result && (
          <>
            <ResultView data={result} onReset={handleReset} />

            <div className="mt-12 space-y-4 border-t border-border pt-8">
              <h2 className="font-heading text-xl font-bold tracking-tight text-text-primary">
                Paste any text. See what the sources say.
              </h2>
              <InputArea
                value={input}
                onChange={setInput}
                onVerify={handleVerify}
                loading={false}
              />
            </div>
          </>
        )}
      </div>
    </main>
  );
}
