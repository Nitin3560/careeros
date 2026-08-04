const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function readError(res: Response, fallback: string) {
  try {
    const err = await res.json();
    return err.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function signup(username: string, password: string) {
  const res = await fetch(`${API_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    throw new Error(await readError(res, "Signup failed"));
  }

  return res.json();
}

export async function login(username: string, password: string) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    throw new Error(await readError(res, "Login failed"));
  }

  return res.json();
}
