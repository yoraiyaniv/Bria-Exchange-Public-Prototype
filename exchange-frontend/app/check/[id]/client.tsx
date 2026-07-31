"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Logo from "@/components/Logo";
import InputArea from "@/components/InputArea";
import ResultView from "@/components/ResultView";
import type { ExchangeResult } from "@/lib/api";
import { verifyStream } from "@/lib/api";
import type { VerifyResponse } from "@/lib/api";

interface CheckResultClientProps {
  data: ExchangeResult;
}

export default function CheckResultClient({ data }: CheckResultClientProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleVerify() {
    if (!input.trim()) return;

    if (!session) {
      sessionStorage.setItem("exchange_pending_input", input.trim());
      router.push("/login");
      return;
    }

    setLoading(true);
    await verifyStream(
      input.trim(),
      {
        onResult(res: VerifyResponse) {
          router.push(`/check/${res.result_id}`);
        },
        onError() {
          setLoading(false);
        },
      },
      session.accessToken
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center bg-background px-4 py-12">
      <div className="w-full max-w-[680px] space-y-8">
        <Logo />
        <ResultView
          data={data}
          onReset={() => router.push("/")}
          resetLabel="Check something with Exchange"
        />

        <div className="mt-12 space-y-4 border-t border-border pt-8">
          <h2 className="font-heading text-xl font-bold tracking-tight text-text-primary">
            Paste any text. See what the sources say.
          </h2>
          <InputArea
            value={input}
            onChange={setInput}
            onVerify={handleVerify}
            loading={loading}
          />
        </div>
      </div>
    </main>
  );
}
