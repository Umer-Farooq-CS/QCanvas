import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Github, Linkedin } from "lucide-react";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/site/SiteFooter";
import { config, type TeamMember } from "@/lib/config";

const FACTS = [
  { term: "Frameworks", detail: "Cirq, Qiskit and PennyLane" },
  { term: "Intermediate format", detail: "OpenQASM 3.0" },
  { term: "Simulation", detail: "QSim backend, plus the Cirq, Qiskit and PennyLane simulators" },
  { term: "Examples", detail: `${config.stats.examples} runnable circuits` },
];

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

const iconLinkClass =
  "qc-focus grid h-8 w-8 place-items-center rounded-md text-qc-subtle transition-colors duration-150 hover:bg-qc-surface-2 hover:text-qc-fg";

/**
 * Emails are wrapped in <!--email_off--> so Cloudflare's email obfuscation
 * leaves the mailto link intact (it otherwise rewrites it into a script).
 */
function EmailLink({ email, name }: { email: string; name: string }) {
  return (
    <span
      dangerouslySetInnerHTML={{
        __html: `<!--email_off--><a href="mailto:${email}" class="${iconLinkClass}" aria-label="Email ${name}"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg></a><!--/email_off-->`,
      }}
    />
  );
}

function IconLink({
  href,
  label,
  children,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={label} className={iconLinkClass}>
      {children}
    </a>
  );
}

function MemberLinks({ member }: { member: TeamMember }) {
  return (
    <div className="-ml-2 mt-auto flex items-center gap-0.5 pt-3">
      {member.github && (
        <IconLink href={member.github} label={`${member.name} on GitHub`}>
          <Github className="h-4 w-4" aria-hidden="true" />
        </IconLink>
      )}
      {member.linkedin && (
        <IconLink href={member.linkedin} label={`${member.name} on LinkedIn`}>
          <Linkedin className="h-4 w-4" aria-hidden="true" />
        </IconLink>
      )}
      {member.email && <EmailLink email={member.email} name={member.name} />}
    </div>
  );
}

function MemberCard({ member }: { member: TeamMember }) {
  // Members with a portrait get a photo card; others a compact row, so
  // there are no large empty placeholders.
  if (!member.image) {
    return (
      <li className="qc-card flex gap-4 p-4 sm:p-5">
        <span
          className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-qc-surface-2 font-display font-semibold text-qc-muted"
          aria-hidden="true"
        >
          {initials(member.name)}
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <h4 className="font-semibold text-qc-fg">{member.name}</h4>
          <p className="text-sm text-qc-subtle">{member.role}</p>
          <p className="mt-2 text-sm leading-relaxed text-qc-muted">{member.bio}</p>
          <MemberLinks member={member} />
        </div>
      </li>
    );
  }

  return (
    <li className="qc-card flex gap-4 overflow-hidden p-4 sm:flex-col sm:gap-0 sm:p-0">
      <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg bg-qc-surface-2 sm:h-56 sm:w-full sm:rounded-none">
        <Image
          src={member.image}
          alt={`Portrait of ${member.name}`}
          fill
          sizes="(min-width: 640px) 360px, 80px"
          className="object-cover object-top"
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col sm:p-5 sm:pt-4">
        <h4 className="font-semibold text-qc-fg">{member.name}</h4>
        <p className="text-sm text-qc-subtle">{member.role}</p>
        <p className="mt-2 text-sm leading-relaxed text-qc-muted">{member.bio}</p>
        <MemberLinks member={member} />
      </div>
    </li>
  );
}

function TeamSection({
  id,
  title,
  description,
  members,
}: {
  id: string;
  title: string;
  description: string;
  members: TeamMember[];
}) {
  return (
    <section aria-labelledby={id} className="mt-14 first:mt-0">
      <h3 id={id} className="text-title font-semibold text-qc-fg">
        {title}
      </h3>
      <p className="mt-1 text-sm text-qc-muted">{description}</p>
      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {members.map((member) => (
          <MemberCard key={member.name} member={member} />
        ))}
      </ul>
    </section>
  );
}

export default function AboutPage() {
  // Don't publish an address that belongs to someone else (a config data
  // issue: see design-audit/AUDIT.md B11).
  const memberEmails = new Map(config.team.map((m) => [m.email, m.name]));
  const supervisors = config.supervisors.map((s) => ({
    ...s,
    email: memberEmails.has(s.email) && memberEmails.get(s.email) !== s.name ? undefined : s.email,
  }));

  return (
    <div className="qc-page">
      <Navbar />

      <main id="main" className="qc-container pb-24 pt-28">
        <header className="grid gap-10 border-b border-qc-line pb-14 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-16">
          <div>
            <p className="qc-eyebrow">About</p>
            <h1 className="mt-3 font-display text-display-1 font-semibold text-qc-fg [text-wrap:balance]">
              A quantum programming IDE, built for the classroom
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-qc-muted">
              Students meet quantum computing through three Python frameworks,
              each with its own way of writing the same circuit. QCanvas puts them
              side by side: write in the one you know, read the OpenQASM 3.0 it
              compiles to, and run it without installing anything.
            </p>
            <p className="mt-4 max-w-2xl leading-relaxed text-qc-muted">
              It is developed at FAST University as part of {config.initiative.name}:
              the QCanvas team builds the editor and converters, and the QSim team
              builds the simulator.
            </p>
          </div>

          <dl className="grid content-start gap-px self-start overflow-hidden rounded-xl border border-qc-line bg-qc-line">
            {FACTS.map((fact) => (
              <div key={fact.term} className="bg-qc-surface px-5 py-4">
                <dt className="text-xs text-qc-subtle">{fact.term}</dt>
                <dd className="mt-1 text-sm text-qc-fg">{fact.detail}</dd>
              </div>
            ))}
          </dl>
        </header>

        <section aria-labelledby="team-heading" className="border-b border-qc-line py-16">
          <h2 id="team-heading" className="font-display text-display-2 font-semibold text-qc-fg">
            The people behind it
          </h2>
          <div className="mt-10">
            <TeamSection
              id="team-qcanvas"
              title="QCanvas team"
              description="The editor, the framework converters and the product as a whole."
              members={config.qcanvasTeam}
            />
            <TeamSection
              id="team-qsim"
              title="QSim team"
              description="The simulation backend and how results are executed and reported."
              members={config.qsimTeam}
            />
          </div>
        </section>

        <section aria-labelledby="supervisors-heading" className="border-b border-qc-line py-16">
          <h2 id="supervisors-heading" className="font-display text-display-2 font-semibold text-qc-fg">
            Supervision
          </h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2">
            {supervisors.map((supervisor) => (
              <li key={supervisor.name} className="qc-card flex items-center gap-4 p-5">
                <span
                  className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-qc-surface-2 font-display font-semibold text-qc-muted"
                  aria-hidden="true"
                >
                  {initials(supervisor.name.replace(/^Dr\.?\s+/, ""))}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-qc-fg">{supervisor.name}</p>
                  <p className="text-sm text-qc-subtle">{supervisor.role}</p>
                </div>
                <div className="flex items-center gap-0.5">
                  {supervisor.linkedin && (
                    <IconLink href={supervisor.linkedin} label={`${supervisor.name} on LinkedIn`}>
                      <Linkedin className="h-4 w-4" aria-hidden="true" />
                    </IconLink>
                  )}
                  {supervisor.email && <EmailLink email={supervisor.email} name={supervisor.name} />}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="contact-heading" className="grid gap-6 pt-16 lg:grid-cols-2 lg:items-end">
          <div>
            <h2 id="contact-heading" className="font-display text-display-2 font-semibold text-qc-fg">
              Get in touch
            </h2>
            <p className="mt-4 max-w-xl text-qc-muted">
              Found a bug, or want to use QCanvas in a course? Open an issue on
              GitHub or email one of the team members above.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <a
              href={config.social.github}
              target="_blank"
              rel="noopener noreferrer"
              className="qc-btn qc-btn-secondary"
            >
              GitHub repository
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
            <Link href="/app" className="qc-btn qc-btn-primary">
              Open the editor
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
