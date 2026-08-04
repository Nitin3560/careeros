"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

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
  };
};

function scoreColor(score: number | null) {
  if (score === null) return "bg-zinc-500";
  if (score >= 60) return "bg-green-700";
  if (score >= 30) return "bg-yellow-600";
  return "bg-red-700";
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
  const observerRef = useRef<HTMLDivElement | null>(null);
  const loadingRef = useRef(false);
  const offsetRef = useRef(0);
  const hasMoreRef = useRef(true);

  useEffect(() => {
    if (checked && !userId) {
      router.push("/");
    }
  }, [checked, router, userId]);

  const loadMore = useCallback(async () => {
    if (!userId || loadingRef.current || !hasMoreRef.current) return;

    loadingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_URL}/users/${userId}/matches?offset=${offsetRef.current}&limit=${PAGE_SIZE}`,
      );
      if (!res.ok) {
        throw new Error("Failed to load matches");
      }

      const data = await res.json();
      const nextOffset = offsetRef.current + PAGE_SIZE;
      offsetRef.current = nextOffset;
      hasMoreRef.current = data.has_more;

      setResults((prev) => [...prev, ...data.results]);
      setOffset(nextOffset);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [userId]);

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
    <main className="mx-auto min-h-screen w-full max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Recommended for you</h1>

      <div className="mt-6 flex flex-col gap-3">
        {results.map((result) => (
          <article
            className="rounded-md border border-zinc-200 p-4"
            key={result.job_id}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">{result.job_title}</h2>
                <p className="mt-1 text-sm text-zinc-600">
                  {result.company}
                  {result.location ? ` - ${result.location}` : ""}
                </p>
              </div>
              <span
                className={`${scoreColor(
                  result.match.overall_score,
                )} shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-sm font-semibold text-white`}
              >
                {result.match.overall_score ?? "Pending"}
              </span>
            </div>

            {result.match.strengths.length > 0 && (
              <p className="mt-3 text-sm text-zinc-700">
                <strong>Strengths:</strong> {result.match.strengths.join(", ")}
              </p>
            )}
            {result.match.missing.length > 0 && (
              <p className="mt-2 text-sm text-zinc-700">
                <strong>Missing:</strong> {result.match.missing.join(", ")}
              </p>
            )}
            {result.match.overall_score === null && (
              <p className="mt-2 text-sm italic text-zinc-500">
                Scoring is temporarily delayed. This job will be retried later.
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="h-10 border border-zinc-300 px-4 text-sm font-medium"
                type="button"
                onClick={() => router.push(`/tailor/${result.job_id}`)}
              >
                Edit resume
              </button>
              {result.application_url && (
                <a
                  className="inline-flex h-10 items-center bg-zinc-950 px-4 text-sm font-medium text-white"
                  href={result.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Apply now
                </a>
              )}
            </div>
          </article>
        ))}
      </div>

      {loading && <p className="mt-4 text-sm text-zinc-600">Loading more matches...</p>}
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      {!hasMore && results.length > 0 && (
        <p className="mt-4 text-sm text-zinc-500">No more matches found.</p>
      )}
      {!loading && results.length === 0 && !error && !hasMore && (
        <p className="mt-4 text-sm text-zinc-600">
          No matches found for this profile yet.
        </p>
      )}
      {!loading && results.length === 0 && !error && hasMore && (
        <p className="mt-4 text-sm text-zinc-600">Preparing matches...</p>
      )}

      <div ref={observerRef} className="h-px" />
      <p className="sr-only">Loaded offset {offset}</p>
    </main>
  );
}
