import { getSupabaseClient } from "@/lib/supabase";

export async function signUp(email: string, password: string) {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase client not initialized");
    }
    return await supabase.auth.signUp({ email, password });
  } catch (error) {
    console.error("Sign up error:", error);
    throw error;
  }
}

export async function signIn(email: string, password: string) {
  try {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase client not initialized");
    }
    if (!supabase.auth || !supabase.auth.signInWithPassword) {
      throw new Error("Supabase auth.signInWithPassword method not available");
    }
    return await supabase.auth.signInWithPassword({ email, password });
  } catch (error) {
    console.error("Sign in error:", error);
    throw error;
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
    console.error("Sign out error:", error);
    throw error;
  }
}
