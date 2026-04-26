import { getSupabaseClient } from "@/lib/supabase";

type LegacySignInAuth = {
  signIn: (credentials: { email: string; password: string }) => Promise<unknown>;
};

type LegacySignInResult = {
  user?: unknown;
  session?: unknown;
  error?: unknown;
};

type AuthResult = {
  data: {
    user: unknown | null;
    session: unknown | null;
  };
  error: Error | unknown | null;
};

function toAuthError(error: unknown): Error {
  const fallbackMessage =
    "Authentication request failed. Verify NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local, then restart the frontend dev server.";

  if (error instanceof Error) {
    const message = error.message?.trim();

    if (message && message.includes("Failed to fetch")) {
      return new Error(fallbackMessage);
    }

    if (message && message !== "{}") {
      return error;
    }

    return new Error(fallbackMessage);
  }

  if (typeof error === "string") {
    if (!error.trim() || error.trim() === "{}") {
      return new Error(fallbackMessage);
    }
    return new Error(error);
  }

  if (typeof error === "object" && error !== null) {
    const candidate = error as {
      message?: unknown;
      error_description?: unknown;
      msg?: unknown;
      hint?: unknown;
      details?: unknown;
    };

    const textCandidates = [
      candidate.message,
      candidate.error_description,
      candidate.msg,
      candidate.hint,
      candidate.details,
    ];

    for (const value of textCandidates) {
      if (typeof value === "string" && value.trim() && value.trim() !== "{}") {
        if (value.includes("Failed to fetch")) {
          return new Error(fallbackMessage);
        }
        return new Error(value);
      }
    }

    return new Error(fallbackMessage);
  }

  return new Error(fallbackMessage);
}

function normalizeAuthResult(result: unknown): AuthResult {
  const authResult = result as {
    data?: { user?: unknown; session?: unknown } | null;
    error?: unknown;
  };

  return {
    data: {
      user: authResult?.data?.user ?? null,
      session: authResult?.data?.session ?? null,
    },
    error: authResult?.error ? toAuthError(authResult.error) : null,
  };
}

export async function signUp(email: string, password: string, fullName: string) {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase client not initialized");
    }
    const normalizedName = fullName.trim();
    return normalizeAuthResult(
      await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: normalizedName,
          },
        },
      }),
    );
  } catch (error) {
    const normalizedError = toAuthError(error);
    return {
      data: {
        user: null,
        session: null,
      },
      error: normalizedError,
    };
  }
}

export async function signIn(email: string, password: string) {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase client not initialized");
    }
    if (typeof supabase.auth?.signInWithPassword === "function") {
      const result = await supabase.auth.signInWithPassword({ email, password }).catch((error: unknown): AuthResult => {
        return {
          data: {
            user: null,
            session: null,
          },
          error: toAuthError(error),
        };
      });

      return normalizeAuthResult(result);
    }

    const legacyAuth = supabase.auth as unknown as Partial<LegacySignInAuth>;
    if (typeof legacyAuth.signIn === "function") {
      const legacyResult = (await legacyAuth.signIn({
        email,
        password,
      })) as LegacySignInResult;

      return normalizeAuthResult({
        data: {
          user: legacyResult.user ?? null,
          session: legacyResult.session ?? null,
        },
        error: legacyResult.error ?? null,
      });
    }

    throw new Error("Supabase auth sign-in method is not available");
  } catch (error) {
    const normalizedError = toAuthError(error);
    return {
      data: {
        user: null,
        session: null,
      },
      error: normalizedError,
    };
  }
}

export async function signOut() {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase client not initialized");
    }
    return await supabase.auth.signOut();
  } catch (error) {
    const normalizedError = toAuthError(error);
    return { error: normalizedError };
  }
}
