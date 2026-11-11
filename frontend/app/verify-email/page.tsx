"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";

import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/authStore";
import Link from "next/link";
import AuthShell, { ButtonSpinner } from "@/components/site/AuthShell";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setAuth, setLoading } = useAuthStore();

  const initialEmail = useMemo(
    () => searchParams.get("email") || "",
    [searchParams],
  );
  const [email, setEmail] = useState(initialEmail);
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [resendSeconds, setResendSeconds] = useState(0);

  useEffect(() => {
    if (!initialEmail) return;
    setEmail(initialEmail);
  }, [initialEmail]);

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = setInterval(() => {
      setResendSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendSeconds]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || otp.length !== 6) {
      toast.error("Enter your email and 6-digit OTP code");
      return;
    }

    setIsLoading(true);
    setLoading(true);
    try {
      const response = await authApi.verifySignupOtp(email, otp);
      if (
        !response.success ||
        !response.data ||
        !response.data.access_token ||
        !response.data.user
      ) {
        throw new Error(response.error || "OTP verification failed");
      }

      setAuth(response.data.user, response.data.access_token);
      toast.success("Email verified successfully");
      router.push("/app");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Verification failed",
      );
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email) {
      toast.error("Enter email first");
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.resendSignupOtp(email);
      if (!response.success || !response.data) {
        throw new Error(response.error || "Resend failed");
      }
      setResendSeconds(response.data.cooldown_seconds || 60);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to resend OTP",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell
      title="Verify your email"
      subtitle="Enter the 6-digit code we sent you. Check your spam folder if it hasn’t arrived after a minute."
      footer={
        <p>
          Wrong email?{" "}
          <Link href="/signup" className="qc-link font-medium">
            Sign up again
          </Link>
        </p>
      }
    >
      <form onSubmit={handleVerify} className="space-y-5">
        <div>
          <label htmlFor="email" className="qc-label">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="qc-input"
            required
          />
        </div>

        <div>
          <label htmlFor="otp" className="qc-label">
            Code
          </label>
          <input
            id="otp"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
            className="qc-input font-mono text-lg tracking-[0.4em]"
            placeholder="000000"
            required
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="qc-btn qc-btn-primary qc-btn-lg w-full"
        >
          {isLoading && <ButtonSpinner />}
          {isLoading ? "Verifying…" : "Verify email"}
        </button>
      </form>

      <button
        type="button"
        onClick={handleResend}
        disabled={isLoading || resendSeconds > 0}
        className="qc-btn qc-btn-quiet mt-3 w-full"
      >
        {resendSeconds > 0 ? `Resend code in ${resendSeconds}s` : "Resend code"}
      </button>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="qc-page" />}>
      <VerifyEmailContent />
    </Suspense>
  );
}
