"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { signIn } from "@/lib/auth";
import { getSupabaseClient } from "@/lib/supabase";

const DEMO_ACCOUNT = {
  email: process.env.NEXT_PUBLIC_DEMO_USER_EMAIL ?? "jane@revive.com",
  password: process.env.NEXT_PUBLIC_DEMO_USER_PASSWORD ?? "123456",
} as const;

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isHydrated, setIsHydrated] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pendingApproval = searchParams.get("pending") === "1";

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    let mounted = true;

    const checkSession = async () => {
      try {
        const supabase = getSupabaseClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (mounted && session) {
          router.replace("/");
        }
      } catch {
        // Supabase env may be missing during initial setup.
      }
    };

    void checkSession();

    return () => {
      mounted = false;
    };
  }, [router]);

  const attemptSignIn = async (targetEmail: string, targetPassword: string) => {
    try {
      const result = await signIn(targetEmail, targetPassword);
      const { data, error } = result;

      if (error) {
        setErrorMessage(error.message || "Unable to sign in. Please try again.");
        return;
      }

      const userId = data?.session?.user?.id;
      if (!userId) {
        setErrorMessage("Unable to read session. Please try again.");
        return;
      }

      const supabase = getSupabaseClient();
      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("is_approved")
        .eq("id", userId)
        .single();

      if (profileError) {
        await supabase.auth.signOut();
        setErrorMessage("Unable to verify account approval. Please contact an admin.");
        return;
      }

      if (!profile?.is_approved) {
        const { data: bootstrapApplied, error: bootstrapError } = await supabase.rpc("bootstrap_first_admin", {
          target_user_id: userId,
        });

        if (!bootstrapError && bootstrapApplied === true) {
          router.replace("/");
          return;
        }

        await supabase.auth.signOut();
        setErrorMessage("Your account is pending admin approval.");
        return;
      }

      router.replace("/");
    } catch (error: any) {
      setErrorMessage(`Unable to sign in: ${error.message || "Unknown error"}. Check Supabase configuration.`);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setErrorMessage(null);

    try {
      await attemptSignIn(email, password);
    } finally {
      setLoading(false);
    }
  };

  const handleUseDemoCredentials = () => {
    setEmail(DEMO_ACCOUNT.email);
    setPassword(DEMO_ACCOUNT.password);
    setErrorMessage(null);
  };

  const handleDemoSignIn = async () => {
    setEmail(DEMO_ACCOUNT.email);
    setPassword(DEMO_ACCOUNT.password);
    setDemoLoading(true);
    setErrorMessage(null);

    try {
      await attemptSignIn(DEMO_ACCOUNT.email, DEMO_ACCOUNT.password);
    } finally {
      setDemoLoading(false);
    }
  };

  if (!isHydrated) {
    return <main className="min-h-screen bg-slate-100 p-6" />;
  }

  return (
    <main className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <div className="mb-4 flex justify-center">
          <img src="/revive-logo.svg" alt="REVIVE logo" className="h-24 w-auto" />
        </div>
        <h1 className="text-2xl font-semibold text-slate-900">Login</h1>
        <p className="mt-1 text-sm text-slate-600">Access REVIVE emergency dashboard.</p>

        {pendingApproval ? (
          <p className="mt-3 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
            Your account is awaiting admin confirmation.
          </p>
        ) : null}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-slate-500"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 outline-none focus:border-slate-500"
            />
          </div>

          {errorMessage ? <p className="text-sm text-red-600">{errorMessage}</p> : null}

          <button
            type="submit"
            disabled={loading || demoLoading}
            className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          New user?{" "}
          <Link className="font-medium text-slate-900 underline" href="/signup">
            Create an account
          </Link>
        </p>

        <div className="mt-6 border-t border-slate-200 pt-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Demo access (optional)</p>
          <p className="mt-1 text-xs text-slate-600">Quick walkthrough account: {DEMO_ACCOUNT.email}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleUseDemoCredentials}
              className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Fill demo login
            </button>
            <button
              type="button"
              onClick={() => void handleDemoSignIn()}
              disabled={demoLoading || loading}
              className="rounded-md border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {demoLoading ? "Signing in..." : "Demo sign in"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-slate-100 p-6" />}>
      <LoginPageContent />
    </Suspense>
  );
}
