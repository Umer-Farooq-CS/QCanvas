"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";

import Link from "next/link";
import { authApi } from "@/lib/api";
import AuthShell, { ButtonSpinner } from "@/components/site/AuthShell";

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resetToken = useMemo(
    () => searchParams.get("token") || "",
    [searchParams],
  );

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!resetToken) {
      toast.error("Missing reset token. Restart the password reset process.");
      return;
    }

    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.completePasswordReset(
        resetToken,
        newPassword,
        confirmPassword,
      );
      if (!response.success || !response.data) {
        throw new Error(response.error || "Unable to reset password");
      }
      toast.success("Password reset successful. Please sign in.");
      router.push("/login");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to reset password",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Use at least 8 characters. You’ll sign in again afterwards."
      footer={
        <p>
          Link expired?{" "}
          <Link href="/forgot-password" className="qc-link font-medium">
            Request a new code
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="new-password" className="qc-label">
            New password
          </label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="qc-input"
            required
          />
        </div>
        <div>
          <label htmlFor="confirm-password" className="qc-label">
            Confirm password
          </label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="qc-input"
            required
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="qc-btn qc-btn-primary qc-btn-lg w-full"
        >
          {isLoading && <ButtonSpinner />}
          {isLoading ? "Updating…" : "Update password"}
        </button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="qc-page" />}>
      <ResetPasswordContent />
    </Suspense>
  );
}
