"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";

/**
 * One click into the editor with a private guest workspace (same flow as the
 * sign-in page's "Try it without an account"). Signed-in users go straight
 * to the editor.
 */
export default function GuestStartButton({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const start = async () => {
    const state = useAuthStore.getState();
    if (hasValidAuth(state)) {
      router.push("/app");
      return;
    }
    setBusy(true);
    try {
      const res = await authApi.guestLogin();
      if (!res.success || !res.data) throw new Error(res.error || "Could not start a guest session");
      state.setAuth(res.data.user, res.data.access_token);
      toast("Guest files are deleted when you log out or after 3 days. Create an account to keep your work.", {
        id: "guest-note",
        duration: 7000,
      });
      router.push("/app");
      return; // stay busy until the editor takes over
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not start a guest session");
    }
    setBusy(false);
  };

  return (
    <button type="button" onClick={start} disabled={busy} aria-busy={busy} className={className}>
      {busy ? "Opening the editor…" : children}
    </button>
  );
}
