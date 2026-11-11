"use client";

import Navbar from "@/components/Navbar";

/**
 * Header for account pages (profile, achievements): the same site navbar as
 * every other page, plus a spacer for its fixed height.
 */
export default function SimpleTopBar() {
  return (
    <>
      <Navbar />
      <div className="h-14" aria-hidden="true" />
    </>
  );
}
