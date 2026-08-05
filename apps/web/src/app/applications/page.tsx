"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuthUser } from "@/lib/useAuthUser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STATUSES = [
  "Applied",
  "OA",
  "Recruiter Screen",
  "Technical",
  "Final",
  "Offer",
  "Rejected",
  "Ghosted",
];

type Application = {
  id: string;
  job_id: string;
  job_title: string;
  company: string;
  status: string;
  notes: string | null;
  applied_at: string;
  updated_at: string;
};

export default function ApplicationsPage() {
  const router = useRouter();
  const { user, checked } = useAuthUser();
  const userId = user?.id ?? null;
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (checked && !userId) {
      router.push("/");
    }
  }, [checked, router, userId]);

  const fetchApplications = useCallback(async () => {
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/users/${userId}/applications`);
      if (!res.ok) {
        throw new Error("Failed to load applications");
      }

      const data = await res.json();
      setApplications(data.applications);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchApplications();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [fetchApplications]);

  async function updateStatus(applicationId: string, status: string) {
    if (!userId) return;

    const res = await fetch(
      `${API_URL}/users/${userId}/applications/${applicationId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    );

    if (res.ok) {
      setApplications((prev) =>
        prev.map((application) =>
          application.id === applicationId
            ? { ...application, status }
            : application,
        ),
      );
    }
  }

  if (!checked || !userId) return null;

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-6 py-10">
      <button
        className="mb-5 text-sm font-medium text-zinc-700 underline"
        type="button"
        onClick={() => router.push("/dashboard")}
      >
        Back to matches
      </button>

      <h1 className="text-2xl font-semibold">My applications</h1>

      {loading && <p className="mt-6 text-sm text-zinc-600">Loading...</p>}
      {error && <p className="mt-6 text-sm text-red-600">{error}</p>}
      {!loading && applications.length === 0 && (
        <p className="mt-6 text-sm text-zinc-600">No applications tracked yet.</p>
      )}

      <div className="mt-6 flex flex-col gap-3">
        {applications.map((application) => (
          <article
            className="flex flex-col gap-4 rounded-md border border-zinc-200 p-4 sm:flex-row sm:items-center sm:justify-between"
            key={application.id}
          >
            <div>
              <h2 className="text-lg font-semibold">{application.job_title}</h2>
              <p className="mt-1 text-sm text-zinc-600">{application.company}</p>
              <p className="mt-1 text-xs text-zinc-500">
                Applied {new Date(application.applied_at).toLocaleDateString()}
              </p>
            </div>

            <select
              className="h-10 border border-zinc-300 px-3 text-sm outline-none focus:border-zinc-900"
              value={application.status}
              onChange={(event) =>
                void updateStatus(application.id, event.target.value)
              }
            >
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </article>
        ))}
      </div>
    </main>
  );
}
