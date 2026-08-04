"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useParams, useRouter } from "next/navigation";

import { getUser } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Experience = {
  title: string;
  company: string;
  duration: string;
  highlights: string[];
};

type Education = {
  degree: string;
  institution: string;
  year: string | null;
};

type ResumeContent = {
  full_name: string;
  summary: string;
  skills: { name: string; evidence?: string[] }[];
  experience: Experience[];
  education: Education[];
};

type TailorSuggestions = {
  priority_skills_to_emphasize: string[];
  bullet_rewrites: { original: string; suggested: string }[];
  sections_to_reorder: string;
  gaps: string[];
};

function getStoredUserId() {
  return getUser()?.id ?? null;
}

function subscribeToUserChanges() {
  return () => {};
}

function friendlyError(message: string) {
  if (message.includes("429") || message.toLowerCase().includes("rate limit")) {
    return "Tailoring is temporarily delayed by the AI provider limit. Try this job again later.";
  }
  return message;
}

export default function TailorPage() {
  const router = useRouter();
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const userId = useSyncExternalStore(subscribeToUserChanges, getStoredUserId, () => null);

  const [jobTitle, setJobTitle] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);
  const [content, setContent] = useState<ResumeContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<TailorSuggestions | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) {
      router.push("/");
    }
  }, [router, userId]);

  useEffect(() => {
    if (!userId || !jobId) return;

    async function loadVersion() {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`${API_URL}/users/${userId}/resume-version/${jobId}`);
        if (!res.ok) {
          throw new Error("Failed to load resume version");
        }

        const data = await res.json();
        setContent(data.content);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
      } finally {
        setLoading(false);
      }
    }

    void loadVersion();
  }, [jobId, userId]);

  useEffect(() => {
    if (!userId || !jobId) return;

    async function loadSuggestions() {
      setSuggestionsLoading(true);
      setSuggestionsError(null);

      try {
        const res = await fetch(`${API_URL}/users/${userId}/tailor/${jobId}`, {
          method: "POST",
        });

        if (!res.ok) {
          const err = await res.json().catch(() => null);
          throw new Error(err?.detail || "Failed to generate tailoring suggestions");
        }

        const data = await res.json();
        setJobTitle(data.job_title);
        setCompany(data.company);
        setSuggestions(data.suggestions);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Something went wrong";
        setSuggestionsError(friendlyError(message));
      } finally {
        setSuggestionsLoading(false);
      }
    }

    void loadSuggestions();
  }, [jobId, userId]);

  const handleSave = useCallback(async () => {
    if (!userId || !content) return;

    setSaving(true);
    setSaveStatus(null);

    try {
      const res = await fetch(`${API_URL}/users/${userId}/resume-version/${jobId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });

      if (!res.ok) {
        throw new Error("Save failed");
      }

      setSaveStatus("Saved");
      window.setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [content, jobId, userId]);

  function updateField<K extends keyof ResumeContent>(
    key: K,
    value: ResumeContent[K],
  ) {
    setContent((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function updateExperience(
    index: number,
    field: keyof Experience,
    value: string | string[],
  ) {
    if (!content) return;

    const updated = [...content.experience];
    updated[index] = { ...updated[index], [field]: value };
    updateField("experience", updated);
  }

  function applyBulletSuggestion(original: string, suggested: string) {
    if (!content) return;

    const updated = content.experience.map((experience) => ({
      ...experience,
      highlights: experience.highlights.map((highlight) =>
        highlight === original ? suggested : highlight,
      ),
    }));
    updateField("experience", updated);
  }

  if (!userId) return null;
  if (loading) {
    return <p className="p-6 text-sm text-zinc-600">Loading editor...</p>;
  }
  if (error) {
    return <p className="p-6 text-sm text-red-600">{error}</p>;
  }
  if (!content) return null;

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-8">
      <button
        className="mb-5 text-sm font-medium text-zinc-700 underline"
        type="button"
        onClick={() => router.push("/dashboard")}
      >
        Back to matches
      </button>

      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Resume editor</h1>
          {jobTitle && (
            <p className="mt-1 text-sm text-zinc-600">
              Tailoring for <strong>{jobTitle}</strong>
              {company ? ` at ${company}` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {saveStatus && <span className="text-sm text-zinc-600">{saveStatus}</span>}
          <button
            className="h-10 bg-zinc-950 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <div className="min-w-0">
          <section className="mb-5">
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              Full name
            </label>
            <input
              className="w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
              type="text"
              value={content.full_name}
              onChange={(event) => updateField("full_name", event.target.value)}
            />
          </section>

          <section className="mb-5">
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              Summary
            </label>
            <textarea
              className="w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
              value={content.summary}
              onChange={(event) => updateField("summary", event.target.value)}
              rows={3}
            />
          </section>

          <section className="mb-5">
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              Skills
            </label>
            <input
              className="w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
              type="text"
              value={content.skills.map((skill) => skill.name).join(", ")}
              onChange={(event) =>
                updateField(
                  "skills",
                  event.target.value
                    .split(",")
                    .map((name) => ({ name: name.trim() }))
                    .filter((skill) => skill.name),
                )
              }
            />
          </section>

          <section>
            <h2 className="text-lg font-semibold">Experience</h2>
            <div className="mt-3 flex flex-col gap-3">
              {content.experience.map((experience, index) => (
                <div className="rounded-md border border-zinc-200 p-3" key={index}>
                  <input
                    className="mb-2 w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
                    type="text"
                    placeholder="Title"
                    value={experience.title}
                    onChange={(event) =>
                      updateExperience(index, "title", event.target.value)
                    }
                  />
                  <input
                    className="mb-2 w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
                    type="text"
                    placeholder="Company"
                    value={experience.company}
                    onChange={(event) =>
                      updateExperience(index, "company", event.target.value)
                    }
                  />
                  <input
                    className="mb-2 w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
                    type="text"
                    placeholder="Duration"
                    value={experience.duration}
                    onChange={(event) =>
                      updateExperience(index, "duration", event.target.value)
                    }
                  />
                  <label className="mb-1 block text-xs font-medium text-zinc-500">
                    Highlights
                  </label>
                  <textarea
                    className="w-full border border-zinc-300 p-2 text-sm outline-none focus:border-zinc-900"
                    value={experience.highlights.join("\n")}
                    onChange={(event) =>
                      updateExperience(
                        index,
                        "highlights",
                        event.target.value.split("\n"),
                      )
                    }
                    rows={4}
                  />
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="min-w-0 rounded-md border border-zinc-200 bg-white p-8 lg:sticky lg:top-6">
          <h2 className="text-xl font-semibold">{content.full_name || "Your name"}</h2>
          {content.summary && <p className="mt-3 text-sm text-zinc-700">{content.summary}</p>}

          {content.skills.length > 0 && (
            <section className="mt-5">
              <h3 className="text-sm font-semibold">Skills</h3>
              <p className="mt-1 text-sm text-zinc-700">
                {content.skills.map((skill) => skill.name).join(", ")}
              </p>
            </section>
          )}

          {content.experience.length > 0 && (
            <section className="mt-5">
              <h3 className="text-sm font-semibold">Experience</h3>
              {content.experience.map((experience, index) => (
                <div className="mt-3" key={index}>
                  <p className="text-sm">
                    <strong>{experience.title}</strong>
                    {experience.company && <span> - {experience.company}</span>}
                  </p>
                  {experience.duration && (
                    <p className="text-xs text-zinc-500">{experience.duration}</p>
                  )}
                  <ul className="mt-1 list-disc pl-5 text-sm text-zinc-700">
                    {experience.highlights.filter(Boolean).map((highlight, itemIndex) => (
                      <li key={itemIndex}>{highlight}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          )}

          {content.education.length > 0 && (
            <section className="mt-5">
              <h3 className="text-sm font-semibold">Education</h3>
              {content.education.map((education, index) => (
                <p className="mt-1 text-sm text-zinc-700" key={index}>
                  {education.degree} - {education.institution}
                  {education.year ? ` (${education.year})` : ""}
                </p>
              ))}
            </section>
          )}
        </div>
      </div>

      <section className="mt-8 border-t border-zinc-200 pt-6">
        <h2 className="text-lg font-semibold">AI suggestions for this job</h2>
        {suggestionsLoading && (
          <p className="mt-3 text-sm text-zinc-600">Generating suggestions...</p>
        )}
        {suggestionsError && (
          <p className="mt-3 text-sm text-zinc-500">{suggestionsError}</p>
        )}
        {suggestions && (
          <div className="mt-4 flex flex-col gap-4">
            {suggestions.priority_skills_to_emphasize.length > 0 && (
              <p className="text-sm text-zinc-700">
                <strong>Emphasize:</strong>{" "}
                {suggestions.priority_skills_to_emphasize.join(", ")}
              </p>
            )}

            {suggestions.bullet_rewrites.map((bullet, index) => (
              <div className="text-sm" key={index}>
                <span className="text-zinc-500">{bullet.original}</span>
                {bullet.original !== bullet.suggested ? (
                  <>
                    <span> - </span>
                    <span>{bullet.suggested}</span>{" "}
                    <button
                      className="ml-2 text-sm font-medium underline"
                      type="button"
                      onClick={() =>
                        applyBulletSuggestion(bullet.original, bullet.suggested)
                      }
                    >
                      Apply
                    </button>
                  </>
                ) : (
                  <span className="text-zinc-500"> (no safe rewrite found)</span>
                )}
              </div>
            ))}

            {suggestions.gaps.length > 0 && (
              <p className="text-sm text-zinc-700">
                <strong>Gaps:</strong> {suggestions.gaps.join(", ")}
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
