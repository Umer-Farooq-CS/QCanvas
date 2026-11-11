"use client";

import { hasValidAuth, useAuthStore } from "@/lib/authStore";

interface OpenExampleButtonProps {
  example: { name: string; content: string };
  className?: string;
  children: React.ReactNode;
  "aria-label"?: string;
}

/**
 * Stores an example in sessionStorage ("pending-example") and sends the user
 * to the editor, or to sign-in first. The editor picks the example up on load.
 */
export default function OpenExampleButton({
  example,
  className,
  children,
  ...rest
}: OpenExampleButtonProps) {
  const { isAuthenticated, token } = useAuthStore();
  const canAccessApp = hasValidAuth({ isAuthenticated, token });

  const open = () => {
    try {
      sessionStorage.setItem("pending-example", JSON.stringify(example));
    } catch {
      // Storage unavailable (private mode); the editor still opens.
    }
    window.location.href = canAccessApp ? "/app" : "/login";
  };

  return (
    <button type="button" onClick={open} className={className} aria-label={rest["aria-label"]}>
      {children}
    </button>
  );
}
