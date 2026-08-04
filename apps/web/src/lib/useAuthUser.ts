"use client";

import { useEffect, useState } from "react";

import { getUser } from "@/lib/auth";

type AuthUser = {
  id: string;
  username: string;
};

export function useAuthUser() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setUser(getUser());
      setChecked(true);
    }, 0);

    return () => window.clearTimeout(timer);
  }, []);

  return { user, checked };
}
