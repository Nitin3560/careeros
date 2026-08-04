const USER_KEY = "careeros_user";

type StoredUser = {
  id: string;
  username: string;
};

export function saveUser(user: StoredUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): StoredUser | null {
  if (typeof window === "undefined") return null;

  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    clearUser();
    return null;
  }
}

export function clearUser() {
  localStorage.removeItem(USER_KEY);
}
