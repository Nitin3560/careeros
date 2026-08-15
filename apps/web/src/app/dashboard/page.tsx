"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { clearUser } from "@/lib/auth";
import { useAuthUser } from "@/lib/useAuthUser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PAGE_SIZE = 10;

type MatchResult = {
  job_id: string;
  job_title: string;
  company: string;
  location: string | null;
  application_url: string | null;
  match: {
    overall_score: number | null;
    strengths: string[];
    missing: string[];
    confidence: string | null;
    estimated?: boolean;
  };
};

function scoreColor(score: number | null) {
  if (score === null) return "bg-zinc-100 text-zinc-600";
  if (score >= 60) return "bg-green-100 text-green-700";
  if (score >= 50) return "bg-green-50 text-green-700";
  if (score >= 30) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, checked } = useAuthUser();
  const userId = user?.id ?? null;
  const [results, setResults] = useState<MatchResult[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalMatches, setTotalMatches] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [applicationStatus, setApplicationStatus] = useState<
    Record<string, string | null>
  >({});
  const observerRef = useRef<HTMLDivElement | null>(null);
  const loadingRef = useRef(false);
  const offsetRef = useRef(0);
  const hasMoreRef = useRef(true);
  const refreshingRef = useRef(false);

  useEffect(() => {
    if (checked && !userId) {
      router.push("/");
    }
  }, [checked, router, userId]);

  useEffect(() => {
    if (!userId) return;

    fetch(`${API_URL}/users/${userId}/matches/count`)
      .then((res) => res.json())
      .then((data) => setTotalMatches(data.total_matches))
      .catch(() => setTotalMatches(null));
  }, [userId]);

  const checkApplicationStatus = useCallback(
    async (jobId: string) => {
      if (!userId) return;

      const res = await fetch(`${API_URL}/users/${userId}/applications/by-job/${jobId}`);
      if (!res.ok) return;

      const data = await res.json();
      setApplicationStatus((prev) => ({
        ...prev,
        [jobId]: data.tracked ? data.status : null,
      }));
    },
    [userId],
  );

  async function markAsApplied(jobId: string) {
    if (!userId) return;

    const res = await fetch(`${API_URL}/users/${userId}/applications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });

    if (res.ok) {
      setApplicationStatus((prev) => ({ ...prev, [jobId]: "Applied" }));
    }
  }

  const refreshPage = useCallback(
    async (pageOffset: number) => {
      if (!userId || refreshingRef.current) return;

      refreshingRef.current = true;
      setRefreshing(true);
      try {
        const res = await fetch(
          `${API_URL}/users/${userId}/matches?offset=${pageOffset}&limit=${PAGE_SIZE}`,
        );
        if (!res.ok) return;

        const data = await res.json();
        setResults((prev) => {
          const next = [...prev];
          data.results.forEach((result: MatchResult, index: number) => {
            next[pageOffset + index] = result;
          });
          return next.filter(Boolean);
        });
      } catch {
        return;
      } finally {
        refreshingRef.current = false;
        setRefreshing(false);
      }
    },
    [userId],
  );

  const loadMore = useCallback(async () => {
    if (
      !userId ||
      loadingRef.current ||
      refreshingRef.current ||
      !hasMoreRef.current
    ) {
      return;
    }

    loadingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_URL}/users/${userId}/matches/cached?offset=${offsetRef.current}&limit=${PAGE_SIZE}`,
      );
      if (!res.ok) {
        throw new Error("Failed to load matches");
      }

      const data = await res.json();
      const currentOffset = offsetRef.current;
      const nextOffset = offsetRef.current + PAGE_SIZE;
      offsetRef.current = nextOffset;
      hasMoreRef.current = data.has_more;

      setResults((prev) => [...prev, ...data.results]);
      data.results.forEach((result: MatchResult) => {
        void checkApplicationStatus(result.job_id);
      });
      setOffset(nextOffset);
      setHasMore(data.has_more);
      void refreshPage(currentOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [checkApplicationStatus, refreshPage, userId]);

  useEffect(() => {
    if (userId && results.length === 0) {
      void loadMore();
    }
  }, [loadMore, results.length, userId]);

  useEffect(() => {
    const element = observerRef.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          void loadMore();
        }
      },
      { rootMargin: "200px" },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [loadMore]);

  if (!checked || !userId) return null;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f5f6f4] px-6 py-10">
      <div className="pointer-events-none absolute -left-28 bottom-[-22rem] h-[34rem] w-[34rem] rounded-full bg-[#e4e9e3]" />
      <div className="pointer-events-none absolute -right-36 top-48 h-[32rem] w-[32rem] rounded-full bg-[#e4ece4]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-72 w-[34rem] bg-[#c4ddc8] opacity-45" />

      <div className="relative mx-auto w-full max-w-[1500px] pb-20">
        <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-semibold tracking-[-0.01em] text-zinc-950">
            Recommended for you
          </h1>
          {totalMatches !== null && (
            <p className="mt-2 text-sm font-medium text-zinc-500">
              {totalMatches} job{totalMatches !== 1 ? "s" : ""} match your profile
            </p>
          )}
          {refreshing && (
            <p className="mt-1 text-xs font-medium text-zinc-400">
              Refreshing scores in the background
            </p>
          )}
        </div>
        <button
          className="h-10 rounded-lg border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300"
          type="button"
          onClick={() => router.push("/applications")}
        >
          My applications
        </button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {results.map((result) => (
          <article
            className="flex min-h-[300px] flex-col rounded-lg border border-zinc-200 bg-white/95 p-5 shadow-[0_10px_28px_rgba(20,20,20,0.06)]"
            key={result.job_id}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="line-clamp-2 text-[17px] font-semibold leading-6 text-zinc-950">
                  {result.job_title}
                </h2>
                <p className="mt-3 text-sm font-medium text-zinc-500">
                  {result.company}
                  {result.location ? `  •  ${result.location}` : ""}
                </p>
              </div>
              <span
                className={`${scoreColor(
                  result.match.overall_score,
                )} shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs font-bold`}
              >
                {result.match.overall_score === null
                  ? "Pending"
                  : `${result.match.overall_score}% match`}
              </span>
            </div>

            <div className="mt-5 flex-1 space-y-3 text-sm leading-6 text-zinc-700">
              {result.match.strengths.length > 0 && (
                <p>
                  <strong className="font-semibold text-zinc-950">Strengths:</strong>{" "}
                  {result.match.strengths.join(", ")}
                </p>
              )}
              {result.match.missing.length > 0 && (
                <p>
                  <strong className="font-semibold text-zinc-950">Missing:</strong>{" "}
                  {result.match.missing.join(", ")}
                </p>
              )}
              {result.match.estimated && (
                <p className="italic text-zinc-500">
                Estimated match - will refine automatically with AI scoring.
              </p>
              )}
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                className="h-9 rounded-md border border-zinc-200 bg-white px-5 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300"
                type="button"
                onClick={() => router.push(`/tailor/${result.job_id}`)}
              >
                View details
              </button>
              {result.application_url && (
                <a
                  className="inline-flex h-9 items-center rounded-md bg-zinc-950 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800"
                  href={result.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Apply now
                </a>
              )}
              {applicationStatus[result.job_id] ? (
                <span className="inline-flex h-9 items-center rounded-md border border-zinc-200 bg-white px-5 text-sm font-semibold text-green-700 shadow-sm">
                  {applicationStatus[result.job_id]}
                </span>
              ) : (
                <button
                  className="h-9 rounded-md border border-zinc-200 bg-white px-5 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300"
                  type="button"
                  onClick={() => void markAsApplied(result.job_id)}
                >
                  I applied
                </button>
              )}
            </div>
          </article>
        ))}
      </div>

      {loading && <p className="mt-6 text-center text-sm text-zinc-600">Loading more matches...</p>}
      {error && <p className="mt-6 text-center text-sm text-red-600">{error}</p>}
      {!hasMore && results.length > 0 && (
        <p className="mt-6 text-center text-sm text-zinc-500">No more matches found.</p>
      )}
      {!loading && results.length === 0 && !error && !hasMore && (
        <p className="mt-6 text-center text-sm text-zinc-600">
          No matches found for this profile yet.
        </p>
      )}
      {!loading && results.length === 0 && !error && hasMore && (
        <p className="mt-6 text-center text-sm text-zinc-600">Preparing matches...</p>
      )}

      <div ref={observerRef} className="h-px" />
      <p className="sr-only">Loaded offset {offset}</p>
      </div>

      <div className="fixed bottom-6 left-6 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-950 text-sm font-semibold text-white shadow-lg">
        {(user?.username || "N").slice(0, 1).toUpperCase()}
      </div>
      <nav className="fixed bottom-6 right-6 flex rounded-xl border border-zinc-200 bg-white/95 p-1 shadow-[0_10px_30px_rgba(20,20,20,0.12)]">
        <button
          className="rounded-lg px-5 py-3 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-100"
          type="button"
          onClick={() => router.push("/profile")}
        >
          Profile
        </button>
        <button
          className="rounded-lg px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-zinc-100"
          type="button"
          onClick={() => router.push("/dashboard")}
        >
          Resume
        </button>
        <button
          className="rounded-lg px-5 py-3 text-sm font-semibold text-zinc-700 transition hover:bg-zinc-100"
          type="button"
          onClick={() => {
            clearUser();
            router.push("/");
          }}
        >
          Logout
        </button>
      </nav>
    </main>
  );
}
