import Link from "next/link";
import Navbar from "@/components/Navbar";

export default function NotFound() {
  return (
    <div className="qc-page flex flex-col">
      <Navbar />
      <main id="main" className="qc-container flex flex-1 flex-col justify-center py-32">
        <p className="qc-eyebrow">404</p>
        <h1 className="mt-3 font-display text-display-2 font-semibold text-qc-fg">
          This page doesn&apos;t exist
        </h1>
        <p className="mt-3 max-w-md text-qc-muted">
          The link may be old or mistyped. The editor, examples and docs are all
          one click away.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/" className="qc-btn qc-btn-primary">
            Go to the home page
          </Link>
          <Link href="/examples" className="qc-btn qc-btn-secondary">
            Browse examples
          </Link>
        </div>
      </main>
    </div>
  );
}
