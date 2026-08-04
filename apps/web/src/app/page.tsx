"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { login, signup } from "@/lib/api";
import { saveUser } from "@/lib/auth";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const user =
        mode === "login"
          ? await login(username, password)
          : await signup(username, password);
      saveUser(user);
      router.push("/profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-6 py-12">
      <h1 className="text-2xl font-semibold">
        {mode === "login" ? "Log in" : "Sign up"}
      </h1>

      <form className="mt-6 flex flex-col gap-3" onSubmit={handleSubmit}>
        <input
          className="h-11 border border-zinc-300 px-3 text-base outline-none focus:border-zinc-900"
          type="text"
          placeholder="Username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
        />
        <input
          className="h-11 border border-zinc-300 px-3 text-base outline-none focus:border-zinc-900"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          className="h-11 bg-zinc-950 px-4 text-base font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={loading}
        >
          {loading ? "Please wait..." : mode === "login" ? "Log in" : "Sign up"}
        </button>
      </form>

      <p className="mt-4 text-sm text-zinc-600">
        {mode === "login" ? "Need an account? " : "Already have an account? "}
        <button
          className="font-medium text-zinc-950 underline"
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError(null);
          }}
        >
          {mode === "login" ? "Sign up" : "Log in"}
        </button>
      </p>
    </main>
  );
}
