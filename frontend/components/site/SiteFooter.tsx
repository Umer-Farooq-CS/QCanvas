import Link from "next/link";
import { config } from "@/lib/config";

const columns: { title: string; links: { name: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Product",
    links: [
      { name: "Editor", href: "/app" },
      { name: "Examples", href: "/examples" },
      { name: "Documentation", href: "/docs" },
    ],
  },
  {
    title: "Project",
    links: [
      { name: "About", href: "/about" },
      { name: "Source on GitHub", href: config.social.github, external: true },
      { name: "OpenQASM 3.0 spec", href: "https://openqasm.com/", external: true },
    ],
  },
  {
    title: "Framework docs",
    links: [
      { name: "Cirq", href: "https://quantumai.google/cirq", external: true },
      { name: "Qiskit", href: "https://docs.quantum.ibm.com/", external: true },
      { name: "PennyLane", href: "https://pennylane.ai/", external: true },
    ],
  },
];

export default function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-qc-line">
      <div className="qc-container grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="max-w-xs">
          <Link href="/" className="qc-focus inline-flex items-center gap-2 rounded-md text-qc-fg">
            <span className="qc-logo h-6 w-6" aria-hidden="true" />
            <span className="font-display text-base font-semibold tracking-tight">QCanvas</span>
          </Link>
          <p className="mt-3 text-sm leading-relaxed text-qc-muted">
            A browser IDE for writing, compiling and simulating quantum circuits.
            Part of {config.initiative.name}, an initiative at FAST University.
          </p>
        </div>

        {columns.map((col) => (
          <div key={col.title}>
            <h2 className="text-xs font-medium text-qc-subtle">{col.title}</h2>
            <ul className="mt-3 space-y-2">
              {col.links.map((link) => (
                <li key={link.name}>
                  {link.external ? (
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="qc-focus rounded text-sm text-qc-muted transition-colors duration-150 hover:text-qc-fg"
                    >
                      {link.name}
                    </a>
                  ) : (
                    <Link
                      href={link.href as never}
                      className="qc-focus rounded text-sm text-qc-muted transition-colors duration-150 hover:text-qc-fg"
                    >
                      {link.name}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="qc-container flex flex-col gap-2 border-t border-qc-line py-6 text-xs text-qc-subtle sm:flex-row sm:items-center sm:justify-between">
        <p>© {year} QCanvas</p>
        <p>
          Version {config.project.version}
        </p>
      </div>
    </footer>
  );
}
