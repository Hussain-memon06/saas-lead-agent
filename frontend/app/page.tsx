import Link from "next/link";
import { Search, Users, Mail, ShieldCheck, ArrowRight } from "lucide-react";
import { QualifyForm } from "@/components/qualify-form";

const STEPS = [
  {
    icon: Search,
    title: "Research",
    body: "Scrapes the company site and searches the web for funding, hiring, and product signals.",
  },
  {
    icon: Users,
    title: "Find decision-maker",
    body: "Looks up the right contact via Hunter.io with seniority and department ranking.",
  },
  {
    icon: Mail,
    title: "Draft email",
    body: "Personalised, three-to-four-sentence outreach grounded in the dossier signals.",
  },
  {
    icon: ShieldCheck,
    title: "You approve",
    body: "Nothing sends without your click. Reject and the pipeline halts cleanly.",
  },
] as const;

const FOOTER_LINKS = [
  { label: "GitHub", href: "https://github.com/Hussain-memon06/saas-lead-agent", external: true },
  { label: "Docs", href: "https://github.com/Hussain-memon06/saas-lead-agent#readme", external: true },
  { label: "Chainlit UI", href: "/chainlit", external: false },
] as const;

export default function HomePage() {
  return (
    <>
      {/* ----- Hero ----- */}
      <section className="relative isolate overflow-hidden">
        {/* Layered backdrop: dotted grid + indigo halo, both fading out */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-grid-dots mask-fade-b"
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-hero-halo" />

        <div className="mx-auto max-w-6xl px-6 pb-24 pt-20 sm:pt-28 lg:pt-36">
          <div className="mx-auto max-w-3xl space-y-8 text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" aria-hidden />
              AI SDR Agent
            </span>
            <h1 className="text-balance text-5xl font-semibold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
              AI-powered B2B lead research, with a human in the loop.
            </h1>
            <p className="text-balance text-lg leading-relaxed text-muted-foreground sm:text-xl">
              Paste a company URL. Get a one-page dossier, a fit score, and a
              personalised outreach email — ready for your approval before send.
            </p>
          </div>

          <div id="qualify" className="mx-auto mt-12 max-w-2xl">
            <QualifyForm />
          </div>

          <p className="mx-auto mt-6 max-w-2xl text-center text-sm text-muted-foreground">
            Typically takes 60–90 seconds. No account required.
          </p>
        </div>
      </section>

      {/* ----- How it works ----- */}
      <section className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
        <div className="mb-12 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            How it works
          </p>
          <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            From URL to ready-to-send email in four steps.
          </h2>
        </div>

        <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="group relative flex flex-col gap-5 rounded-xl border border-border/60 bg-card p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-inset ring-primary/15 transition-colors group-hover:bg-primary/15">
                <step.icon className="h-6 w-6" aria-hidden />
              </div>
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Step {i + 1}
                </p>
                <h3 className="text-lg font-semibold tracking-tight text-foreground">
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ----- CTA ----- */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="relative isolate overflow-hidden rounded-2xl bg-gradient-to-br from-primary via-primary to-indigo-700 px-8 py-16 text-center sm:px-12 sm:py-20">
          <div
            aria-hidden
            className="absolute inset-0 -z-10 opacity-30"
            style={{
              backgroundImage:
                "radial-gradient(rgb(255 255 255 / 0.18) 1px, transparent 1px)",
              backgroundSize: "22px 22px",
            }}
          />
          <h2 className="text-balance text-3xl font-semibold tracking-tight text-primary-foreground sm:text-4xl">
            Ready to research your first lead?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-balance text-base leading-relaxed text-primary-foreground/80 sm:text-lg">
            Drop a company URL and let the agent do the legwork. You stay in
            the loop on every send.
          </p>
          <div className="mt-8">
            <Link
              href="#qualify"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-background px-6 text-sm font-semibold text-primary shadow-md shadow-black/10 transition-transform hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-background focus-visible:ring-offset-2 focus-visible:ring-offset-primary"
            >
              Research a company
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>
        </div>
      </section>

      {/* ----- Footer ----- */}
      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block h-6 w-6 rounded-md bg-primary"
            />
            <span className="font-semibold tracking-tight text-foreground">
              Dossify
            </span>
            <span className="ml-2 text-xs text-muted-foreground">
              Built with LangGraph, FastAPI &amp; Next.js
            </span>
          </div>
          <nav aria-label="Footer">
            <ul className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              {FOOTER_LINKS.map((link) =>
                link.external ? (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ) : (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ),
              )}
            </ul>
          </nav>
        </div>
      </footer>
    </>
  );
}
