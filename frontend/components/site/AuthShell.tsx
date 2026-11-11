"use client";

import Link from "next/link";
import { Sun, Moon } from "lucide-react";
import { useFileStore } from "@/lib/store";

interface AuthShellProps {
  title: string;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  /** Rendered under the card (e.g. "New to QCanvas? Create an account"). */
  footer?: React.ReactNode;
  /** Wider card for longer forms. */
  wide?: boolean;
}

/** Shared frame for sign-in, sign-up and account-recovery pages. */
export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  wide,
}: AuthShellProps) {
  const { theme, toggleTheme } = useFileStore();
  const themeLabel =
    theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  const ThemeIcon = theme === "dark" ? Sun : Moon;

  return (
    <div className="qc-page flex flex-col">
      <header className="qc-container flex h-14 items-center justify-between">
        <Link
          href="/"
          className="qc-focus -ml-1 flex items-center gap-2 rounded-md px-1 py-1 text-qc-fg"
          aria-label="QCanvas home"
        >
          <span className="qc-logo h-7 w-7" aria-hidden="true" />
          <span className="font-display text-[17px] font-semibold tracking-tight">
            QCanvas
          </span>
        </Link>
        <button
          type="button"
          onClick={toggleTheme}
          className="qc-focus grid h-9 w-9 place-items-center rounded-md text-qc-muted transition-colors duration-150 hover:bg-qc-surface-2 hover:text-qc-fg"
          aria-label={themeLabel}
          title={themeLabel}
        >
          <ThemeIcon className="h-4 w-4" aria-hidden="true" />
        </button>
      </header>

      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-8 sm:items-center sm:pt-4">
        <div className={`w-full ${wide ? "max-w-[30rem]" : "max-w-[26rem]"}`}>
          <h1 className="font-display text-[1.75rem] font-semibold leading-tight tracking-[-0.02em] text-qc-fg">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-[15px] leading-relaxed text-qc-muted">
              {subtitle}
            </p>
          )}

          <div className="qc-card mt-8 p-6 shadow-qc sm:p-7">{children}</div>

          {footer && (
            <div className="mt-6 space-y-2 text-center text-sm text-qc-muted">
              {footer}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/** Small inline spinner for submit buttons. */
export function ButtonSpinner() {
  return (
    <span
      className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    />
  );
}

/** "or" divider between the form and an alternative action. */
export function OrDivider() {
  return (
    <div
      className="my-6 flex items-center gap-3 text-xs text-qc-subtle"
      role="separator"
    >
      <span className="h-px flex-1 bg-qc-line" />
      or
      <span className="h-px flex-1 bg-qc-line" />
    </div>
  );
}
