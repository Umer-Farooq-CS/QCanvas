"use client";

import { Suspense, useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import AuthShell from "@/components/site/AuthShell";
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
    <AuthShell
      wide
      title="Admin approval"
      subtitle="Confirming an admin access request."
    >
      <div
        className={`flex items-start gap-3 rounded-lg border p-4 ${
          status === "success"
            ? "border-qc-success/30 bg-qc-success/10"
            : status === "error"
              ? "border-qc-danger/30 bg-qc-danger/10"
              : "border-qc-line bg-qc-surface-2"
        }`}
        role="status"
      >
        {status === "loading" ? (
          <LoaderCircle
            className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-qc-accent"
            aria-hidden="true"
          />
        ) : status === "idle" ? (
          <ShieldCheck
            className="mt-0.5 h-5 w-5 shrink-0 text-qc-accent"
            aria-hidden="true"
          />
        ) : status === "success" ? (
          <CheckCircle2
            className="mt-0.5 h-5 w-5 shrink-0 text-qc-success"
            aria-hidden="true"
          />
        ) : (
          <CircleAlert
            className="mt-0.5 h-5 w-5 shrink-0 text-qc-danger"
            aria-hidden="true"
          />
        )}
        <div>
          <p className="font-medium text-qc-fg">{message}</p>
          <p className="mt-1 text-sm text-qc-muted">
            {status === "success"
              ? "The admin can now sign in with the approved account."
              : status === "error"
                ? "If this link expired, ask the applicant to submit a new request."
                : status === "idle"
                  ? "Nothing has been approved yet."
                  : "Checking the approval token…"}
          </p>
        </div>
      </div>

      {(status === "idle" || status === "loading") && (
        <button
          type="button"
          onClick={() => void approve()}
          disabled={status === "loading"}
          className="qc-btn qc-btn-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === "loading" ? "Approving…" : "Approve admin account"}
        </button>
      )}

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <Link href="/login" className="qc-btn qc-btn-primary flex-1">
          Go to sign in
        </Link>
        <Link href="/signup" className="qc-btn qc-btn-secondary flex-1">
          Regular sign up
        </Link>
      </div>
    </AuthShell>
  );
}

export default function AdminApprovePage() {
  return (
    <Suspense fallback={<div className="qc-page" />}>
      <AdminApproveContent />
    </Suspense>
  );
}
