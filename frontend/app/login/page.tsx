"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { authApi } from "@/lib/api";
import AuthShell, {
  ButtonSpinner,
  OrDivider,
} from "@/components/site/AuthShell";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, token, setAuth, setLoading } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [guestStarting, setGuestStarting] = useState(false);

  // Warm the editor route so the hand-off after sign-in is instant.
  useEffect(() => {
    router.prefetch("/app");
  }, [router]);

  // Where to go after login: honour ?next= (same-origin paths only).
  const getNextPath = () => {
    if (typeof window === "undefined") return "/app";
    const next = new URLSearchParams(window.location.search).get("next");
    // Reject backslashes/control chars (browsers normalise "/\evil.com" to
    // "//evil.com") and anything that resolves to another origin.
    if (!next || !next.startsWith("/") || /[\\\u0000-\u001f]/.test(next)) {
      return "/app";
    }
    try {
      const url = new URL(next, window.location.origin);
      if (url.origin !== window.location.origin) return "/app";
      // Validate the FINAL string: dot-segment normalisation can turn
      // "/.//evil.com" into "//evil.com", which is protocol-relative.
      const path = url.pathname + url.search + url.hash;
      if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/\\")) {
        return "/app";
      }
      return path;
    } catch {
      return "/app";
    }
  };

  // Check if already authenticated (expiry-aware, so a stale token can't
  // bounce the user between /login and /app).
  useEffect(() => {
    if (canAccessApp) {
      router.replace(getNextPath() as Parameters<typeof router.replace>[0]);
    }
  }, [canAccessApp, router]); // eslint-disable-line react-hooks/exhaustive-deps

  // Explain why the user landed here (e.g. session expired).
  useEffect(() => {
    try {
      const msg = sessionStorage.getItem("qcanvas-auth-message");
      if (msg) {
        sessionStorage.removeItem("qcanvas-auth-message");
        toast(msg, { id: "auth-message" });
      }
    } catch {}
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLoading(true);

    try {
      // Basic validation
      if (!formData.email || !formData.password) {
        throw new Error("Please fill in all fields");
      }

      if (!formData.email.includes("@")) {
        throw new Error("Please enter a valid email");
      }

      // No length check on login: the backend has no login minimum and older
      // accounts may have shorter passwords.

      // Call backend login API
      const response = await authApi.login(formData.email, formData.password);

      if (!response.success || !response.data) {
        if (response.error?.toLowerCase().includes("verification")) {
          router.push(
            `/verify-email?email=${encodeURIComponent(formData.email)}`,
          );
          throw new Error("Please verify your email before signing in");
        }
        throw new Error(response.error || "Login failed");
      }

      const { access_token, user } = response.data;

      // Store auth data
      setAuth(user, access_token);

      // Show success message with user's name
      toast.success(`Welcome back, ${user.full_name}!`);

      // Navigate to app
      router.push(getNextPath() as Parameters<typeof router.push>[0]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setIsLoading(true);
    setLoading(true);
    setGuestStarting(true);

    try {
      // Each visitor gets a private, temporary guest workspace (previously
      // everyone shared one demo account and could overwrite each other's files).
      const response = await authApi.guestLogin();

      if (!response.success || !response.data) {
        throw new Error(response.error || "Could not start a demo session");
      }

      const { access_token, user } = response.data;
      setAuth(user, access_token);

      toast.success("You're in! This is your private guest workspace.");
      toast(
        "Guest files are deleted when you log out or after 3 days. Create an account to keep your work.",
        { id: "guest-note", duration: 7000 },
      );

      router.push(getNextPath() as Parameters<typeof router.push>[0]);
      // Stay in the busy state until the editor route takes over.
      return;
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not start a demo session",
      );
    }
    setIsLoading(false);
    setLoading(false);
    setGuestStarting(false);
  };

  return (
    <AuthShell
      title="Sign in to QCanvas"
      subtitle="Pick up where you left off, or try the editor in a private guest workspace."
      footer={
        <>
          <p>
            New to QCanvas?{" "}
            <Link href="/signup" className="qc-link font-medium">
              Create an account
            </Link>
          </p>
          <p className="text-xs text-qc-subtle">
            Teaching a class?{" "}
            <Link href="/admin/signup" className="qc-link">
              Request admin access
            </Link>
          </p>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="email" className="qc-label">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            required
            value={formData.email}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, email: e.target.value }))
            }
            className="qc-input"
            placeholder="you@university.edu"
            disabled={isLoading}
          />
        </div>

        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <label htmlFor="password" className="qc-label mb-0">
              Password
            </label>
            <Link href="/forgot-password" className="qc-link text-xs">
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={formData.password}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  password: e.target.value,
                }))
              }
              className="qc-input pr-11"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="qc-focus absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-qc-subtle transition-colors duration-150 hover:text-qc-fg"
              aria-label={showPassword ? "Hide password" : "Show password"}
              disabled={isLoading}
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Eye className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="qc-btn qc-btn-primary qc-btn-lg w-full"
        >
          {isLoading && <ButtonSpinner />}
          {isLoading ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <OrDivider />

      <button
        type="button"
        onClick={handleDemoLogin}
        disabled={isLoading}
        aria-busy={guestStarting}
        className="qc-btn qc-btn-secondary qc-btn-lg w-full"
      >
        {guestStarting ? "Opening the editor…" : "Try it without an account"}
      </button>
      <p className="mt-3 text-center text-xs leading-relaxed text-qc-subtle">
        You get a private guest workspace. It&apos;s deleted when you log out or after 3 days.
      </p>
    </AuthShell>
  );
}
