"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Code2, LogOut, Trophy, UserRound } from "lucide-react";
import { useAuthStore } from "@/lib/authStore";

function initials(name?: string | null) {
  if (!name) return "QC";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "QC";
}

/** Signed-in account menu for the site navbar. */
export default function UserMenu() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isGuest = user?.role === "demo";

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const logOut = () => {
    setOpen(false);
    clearAuth();
    router.push("/");
  };

  const item =
    "qc-focus flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-qc-fg transition-colors duration-150 hover:bg-qc-surface-2";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="qc-focus flex items-center gap-2 rounded-full border border-qc-line py-1 pl-1 pr-3 text-sm text-qc-fg transition-colors duration-150 hover:border-qc-line-strong"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-qc-accent-solid text-[11px] font-semibold text-qc-on-accent">
          {initials(user?.full_name || user?.username)}
        </span>
        <span className="max-w-[9rem] truncate">{user?.username ?? "Account"}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="qc-menu-in absolute right-0 top-full z-50 mt-2 w-64 origin-top-right rounded-xl border border-qc-line bg-qc-surface p-1.5 shadow-qc"
        >
          <div className="px-2.5 pb-2 pt-1.5">
            <p className="truncate text-sm font-medium text-qc-fg">
              {user?.full_name || user?.username}
            </p>
            <p className="truncate text-xs text-qc-subtle">
              {isGuest ? "Guest workspace" : user?.email}
            </p>
          </div>
          <div className="my-1 h-px bg-qc-line" />
          <Link href="/app" role="menuitem" className={item} onClick={() => setOpen(false)}>
            <Code2 className="h-4 w-4 text-qc-muted" aria-hidden="true" />
            Open editor
          </Link>
          {!isGuest && (
            <>
              <Link href="/profile" role="menuitem" className={item} onClick={() => setOpen(false)}>
                <UserRound className="h-4 w-4 text-qc-muted" aria-hidden="true" />
                Profile
              </Link>
              <Link href="/achievements" role="menuitem" className={item} onClick={() => setOpen(false)}>
                <Trophy className="h-4 w-4 text-qc-muted" aria-hidden="true" />
                Achievements
              </Link>
            </>
          )}
          <div className="my-1 h-px bg-qc-line" />
          <button type="button" role="menuitem" onClick={logOut} className={`${item} text-qc-danger`}>
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Log out
          </button>
          {isGuest && (
            <p className="px-2.5 pb-1.5 pt-1 text-xs leading-relaxed text-qc-subtle">
              Logging out deletes this guest workspace and its files.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
