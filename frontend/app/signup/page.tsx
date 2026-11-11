"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { authApi } from "@/lib/api";
import AuthShell, {
  ButtonSpinner,
  OrDivider,
} from "@/components/site/AuthShell";
import Link from "next/link";

export default function SignupPage() {
  const router = useRouter();
  const { isAuthenticated, token, setAuth, setLoading } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  const [formData, setFormData] = useState({
    fullName: "",
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [guestStarting, setGuestStarting] = useState(false);

  // Warm the editor route so the hand-off after sign-in is instant.
  useEffect(() => {
    router.prefetch("/app");
  }, [router]);

  // Check if already authenticated
  useEffect(() => {
    if (canAccessApp) {
      router.push("/app");
    }
  }, [canAccessApp, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setLoading(true);

    try {
      // Validation
      if (
        !formData.fullName ||
        !formData.username ||
        !formData.email ||
        !formData.password ||
        !formData.confirmPassword
      ) {
        throw new Error("Please fill in all fields");
      }

      if (!formData.email.includes("@")) {
        throw new Error("Please enter a valid email");
      }

      // Must match the backend's register minimum (auth.py).
      if (formData.password.length < 8) {
        throw new Error("Password must be at least 8 characters");
      }

      if (formData.password !== formData.confirmPassword) {
        throw new Error("Passwords do not match");
      }

      // Call backend register API
      const response = await authApi.register({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.fullName,
      });

      if (!response.success || !response.data) {
        throw new Error(response.error || "Registration failed");
      }

      const registerResult = response.data;

      if (registerResult.verification_required) {
        toast.success(
          registerResult.message || "Verification code sent to your email",
        );
        router.push(
          `/verify-email?email=${encodeURIComponent(registerResult.user.email)}`,
        );
        return;
      }

      if (!registerResult.access_token) {
        throw new Error("Registration completed but no access token returned");
      }

      setAuth(registerResult.user, registerResult.access_token);
      toast.success(`Welcome to QCanvas, ${registerResult.user.full_name}`);
      router.push("/app");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Registration failed",
      );
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

      router.push("/app");
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
      title="Create your account"
      subtitle="Save your circuits, track your progress and pick up on any computer."
      footer={
        <>
          <p>
            Already have an account?{" "}
            <Link href="/login" className="qc-link font-medium">
              Sign in
            </Link>
          </p>
          <p className="text-xs text-qc-subtle">
            Teaching a class?{" "}
            <Link href="/admin/signup" className="qc-link">
              Apply for admin access
            </Link>
          </p>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="fullName" className="qc-label">
              Full name
            </label>
            <input
              id="fullName"
              type="text"
              autoComplete="name"
              required
              value={formData.fullName}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, fullName: e.target.value }))
              }
              className="qc-input"
              disabled={isLoading}
            />
          </div>
          <div>
            <label htmlFor="username" className="qc-label">
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={formData.username}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, username: e.target.value }))
              }
              className="qc-input"
              disabled={isLoading}
            />
          </div>
        </div>
        <div>
          <label htmlFor="email" className="qc-label">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
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
          <label htmlFor="password" className="qc-label">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              value={formData.password}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, password: e.target.value }))
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
          <p className="mt-1.5 text-xs text-qc-subtle">
            At least 6 characters.
          </p>
        </div>
        <div>
          <label htmlFor="confirmPassword" className="qc-label">
            Confirm password
          </label>
          <div className="relative">
            <input
              id="confirmPassword"
              type={showConfirmPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              value={formData.confirmPassword}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  confirmPassword: e.target.value,
                }))
              }
              className="qc-input pr-11"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="qc-focus absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-qc-subtle transition-colors duration-150 hover:text-qc-fg"
              aria-label={
                showConfirmPassword ? "Hide password" : "Show password"
              }
              disabled={isLoading}
            >
              {showConfirmPassword ? (
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
          className="qc-btn qc-btn-primary qc-btn-lg mt-2 w-full"
        >
          {isLoading && <ButtonSpinner />}
          {isLoading ? "Creating account…" : "Create account"}
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
    </AuthShell>
  );
}
