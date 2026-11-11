"use client";

import { Suspense, useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle2,
  CircleAlert,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import toast from "react-hot-toast";

import { authApi } from "@/lib/api";

function AdminApproveContent() {
  const searchParams = useSearchParams();
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);

  // Approval is a state-changing action, so it must not run on page load:
  // link-preview bots (mail clients, Slack, etc.) and React StrictMode's double
  // effect invocation would otherwise approve the account without a human.
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >(token ? "idle" : "error");
  const [message, setMessage] = useState(
    token
      ? "Review this request, then approve the admin account."
      : "Approval token is missing from the URL.",
  );
  const inFlightRef = useRef(false);

  const approve = useCallback(async () => {
    if (!token || inFlightRef.current) return;
    inFlightRef.current = true;
    setStatus("loading");
    setMessage("Approving admin account...");

    try {
      const response = await authApi.approveAdmin(token);
      if (!response.success || !response.data) {
        throw new Error(response.error || "Approval failed");
      }

      setStatus("success");
      setMessage(
        response.data.message || "Admin account approved successfully.",
      );
      toast.success("Admin account approved");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Approval failed";
      setStatus("error");
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      inFlightRef.current = false;
    }
  }, [token]);

  return (
    <div className="min-h-screen bg-[#0a0a1a] px-4 py-10 flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 bg-grid-pattern opacity-60" />
      <div className="absolute inset-0 hero-spotlight" />
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -right-32 h-[500px] w-[500px] rounded-full bg-emerald-500/10 blur-[120px]" />
        <div className="absolute -bottom-32 -left-32 h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[120px]" />
      </div>

      <div className="relative z-10 w-full max-w-xl quantum-glass-dark rounded-3xl border border-white/10 p-8 shadow-[0_0_50px_rgba(15,23,42,0.35)]">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-cyan-300">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Approval</h1>
            <p className="text-sm text-gray-300">
              Master admin verification portal
            </p>
          </div>
        </div>

        <div
          className={`rounded-2xl border p-5 ${status === "success" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100" : status === "error" ? "border-red-500/20 bg-red-500/10 text-red-100" : "border-white/10 bg-white/5 text-gray-100"}`}
        >
          <div className="flex items-start gap-3">
            {status === "loading" ? (
              <LoaderCircle className="mt-0.5 h-5 w-5 animate-spin text-cyan-300" />
            ) : status === "idle" ? (
              <ShieldCheck className="mt-0.5 h-5 w-5 text-cyan-300" />
            ) : status === "success" ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-300" />
            ) : (
              <CircleAlert className="mt-0.5 h-5 w-5 text-red-300" />
            )}
            <div>
              <p className="font-medium">{message}</p>
              <p className="mt-2 text-sm opacity-80">
                {status === "success"
                  ? "The admin can now log in with the approved account."
                  : status === "error"
                    ? "If this link expired, ask the admin applicant to submit a new request."
                    : status === "idle"
                      ? "Nothing has been approved yet."
                      : "Please wait while we verify the approval token."}
              </p>
            </div>
          </div>
        </div>

        {(status === "idle" || status === "loading") && (
          <button
            type="button"
            onClick={() => void approve()}
            disabled={status === "loading"}
            className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-emerald-500 px-4 py-3 font-medium text-white transition-colors hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {status === "loading" ? "Approving..." : "Approve admin account"}
          </button>
        )}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/login"
            className="inline-flex flex-1 items-center justify-center rounded-xl bg-indigo-500 px-4 py-3 font-medium text-white transition-colors hover:bg-indigo-600"
          >
            Go to Login
          </Link>
          <Link
            href="/signup"
            className="inline-flex flex-1 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 py-3 font-medium text-white transition-colors hover:bg-white/10"
          >
            Regular Sign Up
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function AdminApprovePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0a0a1a]" />}>
      <AdminApproveContent />
    </Suspense>
  );
}
