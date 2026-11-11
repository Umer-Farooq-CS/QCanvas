"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";

import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import AuthShell, { ButtonSpinner } from "@/components/site/AuthShell";
import { authApi } from "@/lib/api";

export default function AdminSignupPage() {
  const router = useRouter();
  const { isAuthenticated, token, setLoading } = useAuthStore();
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
  const [isSubmitted, setIsSubmitted] = useState(false);

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

      if (formData.password.length < 8) {
        throw new Error("Password must be at least 8 characters");
      }

      if (formData.password !== formData.confirmPassword) {
        throw new Error("Passwords do not match");
      }

      const response = await authApi.registerAdmin({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.fullName,
      });

      if (!response.success || !response.data) {
        throw new Error(response.error || "Admin signup failed");
      }

      setIsSubmitted(true);
      toast.success(
        response.data.message || "Admin request submitted for approval",
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Admin signup failed",
      );
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  return (
    <AuthShell
      wide
      title="Request admin access"
      subtitle="Admin accounts can manage users and review projects. Every request is approved by hand before the account is activated."
      footer={
        <p>
          Not an admin?{" "}
          <Link href="/signup" className="qc-link font-medium">
            Create a regular account
          </Link>
        </p>
      }
    >
      {isSubmitted ? (
        <div className="space-y-5">
          <div className="rounded-lg border border-qc-success/30 bg-qc-success/10 p-4">
            <p className="font-medium text-qc-fg">Request submitted</p>
            <p className="mt-1 text-sm text-qc-muted">
              The master admin has been notified. You can sign in once the
              request is approved.
            </p>
          </div>
          <Link
            href="/login"
            className="qc-btn qc-btn-primary qc-btn-lg w-full"
          >
            Go to sign in
          </Link>
        </div>
      ) : (
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
              At least 8 characters.
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
            {isLoading ? "Submitting…" : "Submit request"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
