import type { Route } from "next";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Reveal from "@/components/site/Reveal";
import { config } from "@/lib/config";

interface Resource {
  label: string;
  note: string;
  href: string;
  external: boolean;
}

const RESOURCES: ReadonlyArray<Resource> = [
  { label: "QCanvas docs", note: "Guides and API", href: "/docs", external: false },
  { label: "Examples", note: "Runnable circuits", href: "/examples", external: false },
  { label: "Source on GitHub", note: "Read and contribute", href: config.social.github, external: true },
  { label: "OpenQASM 3.0 specification", note: "openqasm.com", href: "https://openqasm.com/", external: true },
  { label: "Qiskit docs", note: "docs.quantum.ibm.com", href: "https://docs.quantum.ibm.com/", external: true },
  { label: "Cirq docs", note: "quantumai.google/cirq", href: "https://quantumai.google/cirq", external: true },
  { label: "PennyLane docs", note: "docs.pennylane.ai", href: "https://docs.pennylane.ai/", external: true },
];

function Row({ r }: { r: Resource }) {
  const arrowCls =
    "h-4 w-4 shrink-0 text-qc-subtle transition-[transform,color] duration-150 group-hover:text-qc-accent motion-reduce:transition-none motion-reduce:group-hover:transform-none";
  const inner = (
    <>
      <span className="min-w-0">
        <span className="block text-[0.9375rem] font-medium text-qc-fg underline decoration-transparent decoration-1 underline-offset-4 transition-[text-decoration-color] duration-150 group-hover:decoration-qc-accent motion-reduce:transition-none">
          {r.label}
        </span>
        <span className="mt-0.5 block truncate font-mono text-xs text-qc-subtle">{r.note}</span>
      </span>
      {r.external ? (
        <ArrowUpRight
          aria-hidden="true"
          className={`${arrowCls} group-hover:-translate-y-0.5 group-hover:translate-x-0.5`}
        />
      ) : (
        <ArrowRight aria-hidden="true" className={`${arrowCls} group-hover:translate-x-0.5`} />
      )}
    </>
  );
  const cls =
    "qc-focus group flex items-center justify-between gap-4 rounded-sm border-b border-qc-line py-4";

  return r.external ? (
    <a href={r.href} target="_blank" rel="noopener noreferrer" className={cls}>
      {inner}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ) : (
    <Link href={r.href as Route} className={cls}>
      {inner}
    </Link>
  );
}

export default function ResourcesStrip() {
  return (
    <section className="border-t border-qc-line" aria-labelledby="resources-heading">
      <div className="qc-container py-16 lg:py-20">
        <Reveal>
          <div className="grid gap-8 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] lg:gap-16">
            <div>
              <h2 id="resources-heading" className="font-display text-xl font-semibold text-qc-fg">
                Docs and resources
              </h2>
              <p className="mt-3 text-sm text-qc-muted">
                Start with our docs, then go to the source for each framework and the standard.
              </p>
            </div>
            <ul className="grid gap-x-12 border-t border-qc-line sm:grid-cols-2">
              {RESOURCES.map((r) => (
                <li key={r.href}>
                  <Row r={r} />
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
