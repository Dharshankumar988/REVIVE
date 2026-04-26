import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let supabaseClient: SupabaseClient | null = null;

function normalizeSupabaseUrl(url: string): string {
  const trimmed = url.trim();
  let parsed: URL;

  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL is not a valid URL.");
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL must start with http:// or https://");
  }

  return trimmed.replace(/\/+$/, "");
}

const safeFetch: typeof fetch = async (input, init) => {
  try {
    return await fetch(input, init);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    return new Response(
      JSON.stringify({
        error: "network_error",
        error_description: message,
        message,
      }),
      {
        status: 503,
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
  }
};

export function getSupabaseClient(): SupabaseClient {
  if (supabaseClient) {
    return supabaseClient;
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    throw new Error(
      "Missing frontend Supabase environment variables. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local.",
    );
  }

  try {
    const normalizedUrl = normalizeSupabaseUrl(url);

    supabaseClient = createClient(normalizedUrl, anonKey.trim(), {
      global: {
        fetch: safeFetch,
      },
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });

    // Test the connection
    console.log("Supabase client initialized successfully");

    return supabaseClient;
  } catch (error) {
    console.error("Error initializing Supabase client:", error);
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to initialize Supabase client: ${message}`);
  }
}
