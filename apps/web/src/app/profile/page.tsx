"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuthUser } from "@/lib/useAuthUser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Skill = {
  name?: string;
};

type ParsedProfile = {
  full_name?: string;
  skills?: Skill[];
  experience?: unknown[];
  preferred_roles?: string[];
  parse_warning?: string;
};

export default function ProfilePage() {
  const router = useRouter();
  const { user, checked } = useAuthUser();
  const userId = user?.id ?? null;

  const [file, setFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [parsedProfile, setParsedProfile] = useState<ParsedProfile | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [country, setCountry] = useState("");
  const [remotePreference, setRemotePreference] = useState("any");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (checked && !userId) {
      router.push("/");
    }
  }, [checked, router, userId]);

  async function readError(res: Response, fallback: string) {
    try {
      const err = await res.json();
      return err.detail || fallback;
    } catch {
      return fallback;
    }
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if ((!file && !resumeText.trim()) || !userId) return;

    setUploading(true);
    setUploadError(null);

    const formData = new FormData();
    if (file) {
      formData.append("file", file);
    } else {
      const textFile = new File([resumeText], "pasted-resume.txt", {
        type: "text/plain",
      });
      formData.append("file", textFile);
    }

    try {
      const res = await fetch(`${API_URL}/users/${userId}/resume`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(await readError(res, "Resume upload failed"));
      }

      const profile = await res.json();
      const data = profile.data as ParsedProfile;
      setParsedProfile(data);
      setFullName(data.full_name || "");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveBasicInfo(event: FormEvent) {
    event.preventDefault();
    if (!userId) return;

    setSaving(true);
    setSaveError(null);

    try {
      const res = await fetch(`${API_URL}/users/${userId}/profile/basic-info`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName,
          country,
          remote_preference: remotePreference,
        }),
      });

      if (!res.ok) {
        throw new Error(await readError(res, "Failed to save"));
      }

      router.push("/dashboard");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  if (!checked || !userId) return null;

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#eef2ee] px-6 py-12">
      <div className="absolute -left-44 bottom-[-34rem] h-[58rem] w-[58rem] rounded-full bg-[#dfe5df]" />
      <div className="absolute -right-52 -top-48 h-[42rem] w-[42rem] rounded-full bg-[#d2dbd2]" />
      <div className="absolute bottom-0 right-0 h-72 w-[34rem] bg-[#c4ddc8] opacity-60" />

      <section className="relative w-full max-w-[520px] rounded-xl border border-white/70 bg-white/90 px-11 py-10 shadow-[0_22px_60px_rgba(20,20,20,0.16)]">
        <h1 className="text-[24px] font-semibold text-zinc-950">
          Set up your profile
        </h1>

        {!parsedProfile ? (
          <form className="mt-7 flex flex-col gap-5" onSubmit={handleUpload}>
            <p className="text-sm leading-6 text-zinc-600">
              Upload your resume (.pdf or .txt), or paste the text below.
            </p>
            <label className="flex cursor-pointer flex-col gap-3 rounded-xl border border-zinc-200 bg-white px-5 py-4 text-sm text-zinc-700 shadow-sm transition hover:border-zinc-300">
              <span className="truncate text-base text-zinc-800">
                {file ? file.name : "Choose a PDF or TXT file"}
              </span>
              <input
                className="block w-full text-sm text-zinc-700 file:mr-3 file:rounded-md file:border file:border-zinc-300 file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-zinc-800 hover:file:bg-zinc-50"
                type="file"
                accept=".pdf,.txt"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <textarea
              className="min-h-40 resize-y rounded-xl border border-zinc-200 bg-white px-4 py-4 text-base text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
              placeholder="Or paste your resume text here"
              value={resumeText}
              onChange={(event) => setResumeText(event.target.value)}
            />
            {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
            <button
              className="h-12 rounded-lg bg-zinc-950 px-4 text-base font-medium text-white shadow-[0_8px_18px_rgba(0,0,0,0.18)] transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
              type="submit"
              disabled={uploading || (!file && !resumeText.trim())}
            >
              {uploading ? "Parsing resume..." : "Upload"}
            </button>
          </form>
        ) : (
          <>
            <div className="mt-7 rounded-xl border border-zinc-200 bg-white px-5 py-4 text-sm leading-6 text-zinc-700 shadow-sm">
              {parsedProfile.parse_warning && (
                <p className="mb-3 text-amber-700">
                  Resume uploaded. AI parsing is temporarily limited, so this is
                  a basic extracted profile.
                </p>
              )}
              <p>
                <strong>Extracted skills:</strong>{" "}
                {parsedProfile.skills
                  ?.map((skill) => skill.name)
                  .filter(Boolean)
                  .join(", ") || "None found"}
              </p>
              <p className="mt-2">
                <strong>Experience entries:</strong>{" "}
                {parsedProfile.experience?.length || 0}
              </p>
              <p className="mt-2">
                <strong>Suggested roles:</strong>{" "}
                {parsedProfile.preferred_roles?.join(", ") || "None"}
              </p>
            </div>

            <form
              className="mt-5 flex flex-col gap-3.5"
              onSubmit={handleSaveBasicInfo}
            >
              <input
                className="h-12 rounded-lg border border-zinc-200 bg-white px-4 text-base text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                type="text"
                placeholder="Full name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
              />
              <input
                className="h-12 rounded-lg border border-zinc-200 bg-white px-4 text-base text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                type="text"
                placeholder="Country"
                value={country}
                onChange={(event) => setCountry(event.target.value)}
                required
              />
              <select
                className="h-12 rounded-lg border border-zinc-200 bg-white px-4 text-base text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100"
                value={remotePreference}
                onChange={(event) => setRemotePreference(event.target.value)}
              >
                <option value="any">Any (remote, hybrid, or onsite)</option>
                <option value="remote">Remote only</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">Onsite</option>
              </select>
              {saveError && <p className="text-sm text-red-600">{saveError}</p>}
              <button
                className="h-12 rounded-lg bg-zinc-950 px-4 text-base font-medium text-white shadow-[0_8px_18px_rgba(0,0,0,0.18)] transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={saving}
              >
                {saving ? "Saving..." : "Continue"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
