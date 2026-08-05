"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { clearUser } from "@/lib/auth";
import { useAuthUser } from "@/lib/useAuthUser";

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

function friendlyError(message: string) {
  const lowerMessage = message.toLowerCase();
  if (
    message.includes("429") ||
    lowerMessage.includes("rate limit") ||
    lowerMessage.includes("temporarily unavailable")
  ) {
    return "Tailoring is temporarily delayed by the AI provider limit. Try this job again later.";
  }
  return message;
}

export default function TailorPage() {
  const router = useRouter();
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const { user, checked } = useAuthUser();
  const userId = user?.id ?? null;

  const [jobTitle, setJobTitle] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);
  const [content, setContent] = useState<ResumeContent | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<TailorSuggestions | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);

  useEffect(() => {
    if (checked && !userId) {
      router.push("/");
    }
  }, [checked, router, userId]);

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

      setIsDirty(false);
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
    setIsDirty(true);
  }

  function downloadResume(format: "pdf" | "docx") {
    window.open(
      `${API_URL}/users/${userId}/resume-version/${jobId}/export?format=${format}`,
      "_blank",
    );
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

  function addExperience() {
    if (!content) return;

    updateField("experience", [
      ...content.experience,
      { title: "", company: "", duration: "", highlights: [] },
    ]);
  }

  function removeExperience(index: number) {
    if (!content) return;

    updateField(
      "experience",
      content.experience.filter((_, itemIndex) => itemIndex !== index),
    );
  }

  if (!checked || !userId) return null;
  if (loading) {
    return <p className="p-6 text-sm text-zinc-600">Loading editor...</p>;
  }
  if (error) {
    return <p className="p-6 text-sm text-red-600">{error}</p>;
  }
  if (!content) return null;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f7f8f6] px-6 py-8">
      <div className="pointer-events-none absolute -left-36 bottom-[-24rem] h-[36rem] w-[36rem] rounded-full bg-[#e3e9e3]" />
      <div className="pointer-events-none absolute -right-36 top-44 h-[34rem] w-[34rem] rounded-full bg-[#e9eee8]" />

      <div className="relative mx-auto w-full max-w-[1680px] pb-20">
      <button
        className="mb-5 text-sm font-semibold text-zinc-600 transition hover:text-zinc-950"
        type="button"
        onClick={() => router.push("/dashboard")}
      >
        ← Back to matches
      </button>

      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-[28px] font-semibold tracking-[-0.01em] text-zinc-950">
            Resume editor
          </h1>
          {jobTitle && (
            <p className="mt-2 text-sm font-medium text-zinc-500">
              Tailoring for <strong>{jobTitle}</strong>
              {company ? ` at ${company}` : ""}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {saveStatus && <span className="text-sm text-zinc-600">{saveStatus}</span>}
          <button
            className="h-12 rounded-md bg-zinc-950 px-9 text-sm font-semibold text-white shadow-sm transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            className="h-12 rounded-md border border-zinc-200 bg-white px-8 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            onClick={() => downloadResume("pdf")}
            disabled={isDirty}
            title={isDirty ? "Save your changes first" : ""}
          >
            Download PDF
          </button>
          <button
            className="h-12 rounded-md border border-zinc-200 bg-white px-8 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            onClick={() => downloadResume("docx")}
            disabled={isDirty}
            title={isDirty ? "Save your changes first" : ""}
          >
            Download Word
          </button>
          {isDirty && (
            <span className="text-sm text-amber-700">
              Unsaved changes - save before downloading
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <div className="min-w-0 rounded-lg border border-zinc-200 bg-white/95 p-4 shadow-[0_10px_28px_rgba(20,20,20,0.06)]">
          <section className="mb-5">
            <label className="mb-2 block text-xs font-semibold text-zinc-500">
              Full name
            </label>
            <input
              className="h-11 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
              type="text"
              value={content.full_name}
              onChange={(event) => updateField("full_name", event.target.value)}
            />
          </section>

          <section className="mb-5">
            <label className="mb-2 block text-xs font-semibold text-zinc-500">
              Summary
            </label>
            <textarea
              className="w-full rounded-md border border-zinc-200 bg-white p-3 text-sm font-medium leading-6 text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
              value={content.summary}
              onChange={(event) => updateField("summary", event.target.value)}
              rows={3}
            />
          </section>

          <section className="mb-5">
            <label className="mb-2 block text-xs font-semibold text-zinc-500">
              Skills
            </label>
            <textarea
              className="w-full rounded-md border border-zinc-200 bg-white p-3 text-sm font-medium leading-6 text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
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
              rows={4}
            />
          </section>

          <section>
            <h2 className="text-lg font-semibold text-zinc-950">Experience</h2>
            <div className="mt-3 flex flex-col gap-3">
              {content.experience.map((experience, index) => (
                <div className="rounded-lg border border-zinc-200 p-3" key={index}>
                  <div className="grid gap-4 md:grid-cols-[0.85fr_1.15fr]">
                    <div className="space-y-3">
                      <label className="block">
                        <span className="mb-1 block text-xs font-semibold text-zinc-500">
                          Job title
                        </span>
                        <input
                          className="h-10 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                          type="text"
                          value={experience.title}
                          onChange={(event) =>
                            updateExperience(index, "title", event.target.value)
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs font-semibold text-zinc-500">
                          Organization
                        </span>
                        <input
                          className="h-10 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                          type="text"
                          value={experience.company}
                          onChange={(event) =>
                            updateExperience(index, "company", event.target.value)
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-xs font-semibold text-zinc-500">
                          Duration
                        </span>
                        <input
                          className="h-10 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                          type="text"
                          value={experience.duration}
                          onChange={(event) =>
                            updateExperience(index, "duration", event.target.value)
                          }
                        />
                      </label>
                    </div>
                    <div className="border-zinc-200 md:border-l md:pl-4">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="text-xs font-semibold text-zinc-500">
                          Highlights
                        </span>
                        <button
                          className="h-8 w-8 rounded-md border border-zinc-200 text-sm font-semibold text-zinc-600 transition hover:border-zinc-300"
                          type="button"
                          onClick={() => removeExperience(index)}
                          aria-label="Remove experience"
                        >
                          ×
                        </button>
                      </div>
                      <textarea
                        className="w-full rounded-md border border-zinc-200 bg-white p-3 text-sm font-medium leading-6 text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                        value={experience.highlights.join("\n")}
                        onChange={(event) =>
                          updateExperience(
                            index,
                            "highlights",
                            event.target.value.split("\n"),
                          )
                        }
                        rows={5}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <button
              className="mt-3 h-9 rounded-md border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-900 shadow-sm transition hover:border-zinc-300"
              type="button"
              onClick={addExperience}
            >
              + Add experience
            </button>
          </section>
        </div>

        <div className="min-w-0 rounded-lg border border-zinc-200 bg-white/95 p-3 shadow-[0_10px_28px_rgba(20,20,20,0.06)] lg:sticky lg:top-6">
          <div className="flex items-center justify-between px-3 py-2">
            <h2 className="text-lg font-semibold text-zinc-950">Live preview</h2>
            <div className="flex gap-3 text-xl text-zinc-600">
              <span>▭</span>
              <span className="text-zinc-300">▯</span>
            </div>
          </div>
          <div className="min-h-[760px] rounded-lg border border-zinc-200 bg-white px-8 py-10 font-serif text-zinc-950">
            <h2 className="text-3xl font-bold">{content.full_name || "Your name"}</h2>
            <p className="mt-2 text-sm">
              nrx3560@mavs.uta.edu <span className="px-3">|</span> +1(214) 518-5164{" "}
              <span className="px-3">|</span> www.linkedin.com/in/nitin-singh-rathore{" "}
              <span className="px-3">|</span> github.com/Nitin3560
            </p>

            {content.education.length > 0 && (
              <section className="mt-7">
                <h3 className="border-b-2 border-zinc-600 pb-1 text-sm font-bold tracking-wide">
                  EDUCATION
                </h3>
                {content.education.map((education, index) => (
                  <div className="mt-3 text-sm" key={index}>
                    <div className="flex justify-between gap-4">
                      <p className="font-bold">{education.degree}</p>
                      {education.year && <p>{education.year}</p>}
                    </div>
                    <p className="italic">{education.institution}</p>
                  </div>
                ))}
              </section>
            )}

            {content.experience.length > 0 && (
              <section className="mt-7">
                <h3 className="border-b-2 border-zinc-600 pb-1 text-sm font-bold tracking-wide">
                  EXPERIENCE
                </h3>
                {content.experience.map((experience, index) => (
                  <div className="mt-5 text-sm leading-6" key={index}>
                    <div className="flex justify-between gap-4">
                      <p>
                        <strong>{experience.title}</strong>
                        {experience.company && <span> — {experience.company}</span>}
                      </p>
                      {experience.duration && <p>{experience.duration}</p>}
                    </div>
                    <ul className="mt-1 list-disc pl-5">
                      {experience.highlights.filter(Boolean).map((highlight, itemIndex) => (
                        <li key={itemIndex}>{highlight}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </section>
            )}

            {content.summary && (
              <section className="mt-7">
                <h3 className="border-b-2 border-zinc-600 pb-1 text-sm font-bold tracking-wide">
                  SUMMARY
                </h3>
                <p className="mt-3 text-sm leading-6">{content.summary}</p>
              </section>
            )}

            {content.skills.length > 0 && (
              <section className="mt-7">
                <h3 className="border-b-2 border-zinc-600 pb-1 text-sm font-bold tracking-wide">
                  SKILLS
                </h3>
                <p className="mt-3 text-sm leading-6">
                  {content.skills.map((skill) => skill.name).join(", ")}
                </p>
              </section>
            )}
          </div>
        </div>
      </div>

      <section className="mt-1 rounded-lg border border-zinc-200 bg-white/95 p-4 shadow-[0_10px_28px_rgba(20,20,20,0.06)] lg:w-[calc(50%-0.75rem)]">
        <h2 className="text-lg font-semibold text-zinc-950">
          AI suggestions for this job
        </h2>
        {suggestionsLoading && (
          <p className="mt-3 text-sm text-zinc-600">Generating suggestions...</p>
        )}
        {suggestionsError && (
          <p className="mt-3 text-sm text-zinc-500">{suggestionsError}</p>
        )}
        {suggestions && (
          <div className="mt-4 overflow-hidden rounded-md border border-zinc-200 text-sm">
            {suggestions.priority_skills_to_emphasize.length > 0 && (
              <div className="grid grid-cols-[150px_1fr_72px] border-b border-zinc-200">
                <div className="bg-zinc-50 px-3 py-3 font-semibold text-zinc-700">
                  Emphasize
                </div>
                <div className="px-3 py-3 text-zinc-700">
                  {suggestions.priority_skills_to_emphasize.join(", ")}
                </div>
                <div />
              </div>
            )}

            {suggestions.bullet_rewrites.map((bullet, index) => (
              <div className="grid grid-cols-[150px_1fr_72px] border-b border-zinc-200 last:border-b-0" key={index}>
                <div className="bg-zinc-50 px-3 py-3 font-semibold text-zinc-700">
                  Strengthen
                </div>
                <div className="px-3 py-3 text-zinc-700">
                  {bullet.original !== bullet.suggested ? bullet.suggested : bullet.original}
                </div>
                <div className="flex items-center justify-center border-l border-zinc-200">
                  {bullet.original !== bullet.suggested ? (
                    <button
                      className="font-semibold text-zinc-900"
                      type="button"
                      onClick={() =>
                        applyBulletSuggestion(bullet.original, bullet.suggested)
                      }
                    >
                      Apply
                    </button>
                  ) : (
                    <span className="text-xs text-zinc-400">Safe</span>
                  )}
                </div>
              </div>
            ))}

            {suggestions.gaps.length > 0 && (
              <div className="grid grid-cols-[150px_1fr_72px]">
                <div className="bg-zinc-50 px-3 py-3 font-semibold text-zinc-700">
                  Fill gaps
                </div>
                <div className="px-3 py-3 text-zinc-700">
                  {suggestions.gaps.join(", ")}
                </div>
                <div />
              </div>
            )}
          </div>
        )}
      </section>
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
          className="rounded-lg bg-zinc-100 px-5 py-3 text-sm font-semibold text-zinc-950"
          type="button"
          onClick={() => router.push(`/tailor/${jobId}`)}
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
