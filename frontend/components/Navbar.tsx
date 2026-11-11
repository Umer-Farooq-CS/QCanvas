"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, Sun, Moon } from "lucide-react";
import { useFileStore } from "@/lib/store";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";

const NAV_LINKS = [
  { name: "Examples", path: "/examples" },
  { name: "Docs", path: "/docs" },
  { name: "About", path: "/about" },
] as const;

export default function Navbar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useFileStore();
  const { isAuthenticated, token } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close the mobile menu on navigation and on Escape.
  useEffect(() => setIsMenuOpen(false), [pathname]);
  useEffect(() => {
    if (!isMenuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setIsMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isMenuOpen]);

  const isActive = (path: string) => pathname === path || pathname?.startsWith(path + "/");
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b transition-colors duration-200 ${
        scrolled || isMenuOpen
          ? "border-qc-line bg-qc-bg/95"
          : "border-transparent bg-qc-bg/0"
      }`}
    >
      <nav className="qc-container flex h-14 items-center justify-between gap-4" aria-label="Main">
        <Link
          href="/"
          className="qc-focus -ml-1 flex items-center gap-2 rounded-md px-1 py-1 text-qc-fg"
          aria-label="QCanvas home"
        >
          <span className="qc-logo h-7 w-7" aria-hidden="true" />
          <span className="font-display text-[17px] font-semibold tracking-tight">QCanvas</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((item) => (
            <Link
              key={item.path}
              href={item.path}
              aria-current={isActive(item.path) ? "page" : undefined}
              className={`qc-focus rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
                isActive(item.path)
                  ? "text-qc-fg"
                  : "text-qc-muted hover:text-qc-fg"
              }`}
            >
              {item.name}
            </Link>
          ))}
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <button
            type="button"
            onClick={toggleTheme}
            className="qc-focus grid h-9 w-9 place-items-center rounded-md text-qc-muted transition-colors duration-150 hover:bg-qc-surface-2 hover:text-qc-fg"
            aria-label={themeLabel}
            title={themeLabel}
          >
            <ThemeIcon className="h-4 w-4" aria-hidden="true" />
          </button>
          {canAccessApp ? (
            <Link href="/app" className="qc-btn qc-btn-primary qc-btn-sm">
              Open editor
            </Link>
          ) : (
            <>
              <Link href="/login" className="qc-btn qc-btn-quiet qc-btn-sm">
                Sign in
              </Link>
              <Link href="/signup" className="qc-btn qc-btn-primary qc-btn-sm">
                Create account
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsMenuOpen((open) => !open)}
          className="qc-focus -mr-1 grid h-10 w-10 place-items-center rounded-md text-qc-fg md:hidden"
          aria-expanded={isMenuOpen}
          aria-controls="mobile-nav"
          aria-label={isMenuOpen ? "Close menu" : "Open menu"}
        >
          {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {isMenuOpen && (
        <div id="mobile-nav" className="qc-fade-in border-t border-qc-line bg-qc-bg md:hidden">
          <div className="qc-container flex flex-col py-3">
            {NAV_LINKS.map((item) => (
              <Link
                key={item.path}
                href={item.path}
                aria-current={isActive(item.path) ? "page" : undefined}
                className={`qc-focus rounded-md px-2 py-3 text-[15px] ${
                  isActive(item.path) ? "text-qc-fg" : "text-qc-muted"
                }`}
              >
                {item.name}
              </Link>
            ))}
            <div className="mt-2 flex items-center gap-2 border-t border-qc-line pt-4">
              <button
                type="button"
                onClick={toggleTheme}
                className="qc-btn qc-btn-secondary qc-btn-sm"
                aria-label={themeLabel}
              >
                <ThemeIcon className="h-4 w-4" aria-hidden="true" />
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <div className="ml-auto flex items-center gap-2">
                {canAccessApp ? (
                  <Link href="/app" className="qc-btn qc-btn-primary qc-btn-sm">
                    Open editor
                  </Link>
                ) : (
                  <>
                    <Link href="/login" className="qc-btn qc-btn-quiet qc-btn-sm">
                      Sign in
                    </Link>
                    <Link href="/signup" className="qc-btn qc-btn-primary qc-btn-sm">
                      Create account
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
