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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#eef2ee] px-6 py-12">
      <div className="absolute -left-44 bottom-[-34rem] h-[58rem] w-[58rem] rounded-full bg-[#dfe5df]" />
      <div className="absolute -right-52 -top-48 h-[42rem] w-[42rem] rounded-full bg-[#d2dbd2]" />
      <div className="absolute bottom-0 right-0 h-72 w-[34rem] bg-[#c4ddc8] opacity-60" />

      <section className="relative w-full max-w-[380px] rounded-xl border border-white/70 bg-white/90 px-11 py-10 shadow-[0_22px_60px_rgba(20,20,20,0.16)]">
        <h1 className="text-[22px] font-semibold text-zinc-950">
          {mode === "login" ? "Log in" : "Sign up"}
        </h1>

        <form className="mt-7 flex flex-col gap-3.5" onSubmit={handleSubmit}>
          <input
            className="h-12 rounded-lg border border-zinc-200 bg-white px-4 text-base text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
            type="text"
            placeholder="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          <input
            className="h-12 rounded-lg border border-zinc-200 bg-white px-4 text-base text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            className="mt-1 h-12 rounded-lg bg-zinc-950 px-4 text-base font-medium text-white shadow-[0_8px_18px_rgba(0,0,0,0.18)] transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Log in"
                : "Sign up"}
          </button>
        </form>

        <p className="mt-5 text-sm text-zinc-500">
          {mode === "login" ? "Need an account? " : "Already have an account? "}
          <button
            className="font-medium text-zinc-950 underline underline-offset-2"
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </p>
      </section>
    </main>
  );
}
