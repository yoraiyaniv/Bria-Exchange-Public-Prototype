"use client";

import { useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingText, setPendingText] = useState<string | null>(null);

  useEffect(() => {
    const pending = sessionStorage.getItem("exchange_pending_input");
    if (pending) setPendingText(pending);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    if (mode === "signup") {
      try {
        const res = await fetch("/api/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            email,
            password,
            orgName: name,
          }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(
            data.detail?.error || data.error || "Signup failed. Try again."
          );
          setLoading(false);
          return;
        }
      } catch {
        setError("Something went wrong. Please try again.");
        setLoading(false);
        return;
      }
    }

    const result = await signIn("credentials", {
      redirect: false,
      email,
      password,
    });

    setLoading(false);
    if (result?.error) {
      setError(
        mode === "signup"
          ? "Account created. Please sign in."
          : "Invalid email or password."
      );
      if (mode === "signup") setMode("login");
    } else {
      router.push("/");
    }
  }

  function handleGoogle() {
    signIn("google", { callbackUrl: "/" });
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-[400px] space-y-8">
        <div className="text-center">
          <div className="flex justify-center">
            <Logo />
          </div>
          {pendingText && (
            <div className="mt-4 card-elevated p-3">
              <p className="font-body text-xs text-text-muted mb-1">Your text is ready to verify:</p>
              <p className="font-body text-sm text-text-secondary line-clamp-2">
                {pendingText}
              </p>
            </div>
          )}
          <p className="mt-3 font-body text-sm text-text-secondary">
            {mode === "signup"
              ? "Create a free account to verify your text."
              : "Sign in to continue."}
          </p>
        </div>

        <button
          onClick={handleGoogle}
          className="flex w-full items-center justify-center gap-2 rounded-full border border-border px-4 py-2.5 font-body text-sm font-semibold text-text-primary transition-colors hover:border-bria-purple hover:bg-bria-purple/10"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
          Continue with Google
        </button>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="font-body text-xs text-text-muted">or</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="mb-1 block font-body text-sm font-semibold text-text-primary">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full rounded-lg border border-input bg-transparent px-3 py-2 font-body text-sm text-text-primary placeholder:text-text-muted focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/50"
              />
            </div>
          )}
          <div>
            <label className="mb-1 block font-body text-sm font-semibold text-text-primary">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded-lg border-[1.5px] border-border bg-surface-1 px-3 py-2 font-body text-sm text-text-primary placeholder:text-text-muted focus:border-bria-purple focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block font-body text-sm font-semibold text-text-primary">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded-lg border-[1.5px] border-border bg-surface-1 px-3 py-2 font-body text-sm text-text-primary placeholder:text-text-muted focus:border-bria-purple focus:outline-none"
            />
          </div>

          {error && (
            <p className="font-body text-sm text-[#E8354A]">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-full bg-bria-purple px-4 py-2.5 font-body text-sm font-semibold text-white transition-colors hover:bg-bria-purple-2 disabled:opacity-50"
          >
            {loading
              ? "Loading..."
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="text-center font-body text-sm text-text-secondary">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <button
                onClick={() => { setMode("login"); setError(null); }}
                className="font-semibold text-bria-purple-2 hover:text-bria-purple"
              >
                Sign in
              </button>
            </>
          ) : (
            <>
              Don&apos;t have an account?{" "}
              <button
                onClick={() => { setMode("signup"); setError(null); }}
                className="font-semibold text-bria-purple-2 hover:text-bria-purple"
              >
                Sign up
              </button>
            </>
          )}
        </p>
      </div>
    </main>
  );
}
