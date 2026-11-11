"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";

import { authApi } from "@/lib/api";
import AuthShell, { ButtonSpinner } from "@/components/site/AuthShell";

export default function ForgotPasswordPage() {
  const router = useRouter();

  const [step, setStep] = useState<"send" | "verify">("send");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [resendSeconds, setResendSeconds] = useState(0);

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = setInterval(
      () => setResendSeconds((prev) => (prev > 0 ? prev - 1 : 0)),
      1000,
    );
    return () => clearInterval(timer);
  }, [resendSeconds]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const response = await authApi.sendPasswordResetOtp(email);
      if (!response.success || !response.data) {
        throw new Error(response.error || "Unable to send reset code");
      }
      toast.success(response.data.message);
      setStep("verify");
      setResendSeconds(60);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to send reset code",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const response = await authApi.verifyPasswordResetOtp(email, otp);
      if (!response.success || !response.data?.reset_token) {
        throw new Error(response.error || "Invalid code");
      }
      toast.success("Code verified. Set your new password.");
      router.push(
        `/reset-password?token=${encodeURIComponent(response.data.reset_token)}`,
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to verify code",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendSeconds > 0) return;
    setIsLoading(true);
    try {
      const response = await authApi.sendPasswordResetOtp(email);
      if (!response.success || !response.data) {
        throw new Error(response.error || "Unable to resend reset code");
      }
      toast.success(response.data.message);
      setResendSeconds(60);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to resend code",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell
      title={step === "send" ? "Reset your password" : "Check your email"}
      subtitle={
        step === "send"
          ? "Enter the email you signed up with and we’ll send you a 6-digit code."
          : `We sent a 6-digit code to ${email || "your email"}. It expires shortly.`
      }
      footer={
        <p>
          Remembered it?{" "}
          <Link href="/login" className="qc-link font-medium">
            Back to sign in
          </Link>
        </p>
      }
    >
      {step === "send" ? (
        <form onSubmit={handleSend} className="space-y-5">
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
              placeholder="you@university.edu"
              required
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="qc-btn qc-btn-primary qc-btn-lg w-full"
          >
            {isLoading && <ButtonSpinner />}
            {isLoading ? "Sending…" : "Send reset code"}
          </button>
        </form>
      ) : (
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
            {isLoading ? "Verifying…" : "Verify code"}
          </button>
          <button
            type="button"
            onClick={handleResend}
            disabled={isLoading || resendSeconds > 0}
            className="qc-btn qc-btn-quiet w-full"
          >
            {resendSeconds > 0
              ? `Resend code in ${resendSeconds}s`
              : "Resend code"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
