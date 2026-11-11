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

  // Where to go after login: honour ?next= (same-origin paths only).
  const getNextPath = () => {
    if (typeof window === "undefined") return "/app";
    const next = new URLSearchParams(window.location.search).get("next");
    return next && next.startsWith("/") && !next.startsWith("//")
      ? next
      : "/app";
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

      if (formData.password.length < 6) {
        throw new Error("Password must be at least 6 characters");
      }

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
    setFormData({
      email: "demo@qcanvas.dev",
      password: "demo123",
    });

    // Auto-submit after filling form
    setIsLoading(true);
    setLoading(true);

    try {
      const response = await authApi.login("demo@qcanvas.dev", "demo123");

      if (!response.success || !response.data) {
        throw new Error(response.error || "Demo login failed");
      }

      const { access_token, user } = response.data;
      setAuth(user, access_token);

      toast.success("Signed in with the demo account");
      toast("Demo data will be cleared on logout", { id: "demo-note" });

      router.push(getNextPath() as Parameters<typeof router.push>[0]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Demo login failed");
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Sign in to QCanvas"
      subtitle="Pick up where you left off, or try the editor with the demo account."
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
        className="qc-btn qc-btn-secondary qc-btn-lg w-full"
      >
        Continue with the demo account
      </button>
      <p className="mt-3 text-center text-xs leading-relaxed text-qc-subtle">
        The demo account is shared. Don&apos;t keep anything private in it.
      </p>
    </AuthShell>
  );
}
