import Link from "next/link";
import {
  Search,
  Users,
  Mail,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { QualifyForm } from "@/components/qualify-form";

const STEPS = [
  {
    icon: Search,
    title: "Research company",
    body: "Reads the company site and searches the web for hiring, funding, product, and market signals.",
  },
  {
    icon: Users,
    title: "Find decision-maker",
    body: "Looks up a likely contact with seniority and department context for outbound review.",
  },
  {
    icon: Mail,
    title: "Draft outreach",
    body: "Creates a short outreach draft grounded in the dossier, fit signals, and source context.",
  },
  {
    icon: ShieldCheck,
    title: "Human approval",
    body: "Nothing sends without approval. Reject and the workflow pauses cleanly before outreach.",
  },
] as const;

const FOOTER_LINKS = [
  { label: "GitHub", href: "https://github.com/Hussain-memon06/saas-lead-agent", external: true },
  { label: "Docs", href: "https://github.com/Hussain-memon06/saas-lead-agent#readme", external: true },
  { label: "Chainlit UI", href: "/chainlit", external: false },
] as const;

const CONSOLE_STAGES = [
  { label: "Profile verified", detail: "Sources attached" },
  { label: "Fit logic visible", detail: "Score explained" },
  { label: "Approval gate", detail: "Nothing sends automatically" },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="relative isolate overflow-hidden border-b border-border/40">
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-grid-dots mask-fade-b"
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-hero-halo" />

        <div className="mx-auto grid max-w-7xl gap-12 px-6 pb-16 pt-14 sm:pt-20 lg:grid-cols-[minmax(0,1fr)_480px] lg:items-start lg:gap-16 lg:pb-20 lg:pt-24">
          <div className="max-w-3xl space-y-7">
            <div className="hf-enter flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                Outbound Lead Agent
              </span>
            </div>
            <h1 className="hf-enter hf-enter-1 max-w-4xl text-balance text-5xl font-semibold tracking-tight text-foreground sm:text-6xl lg:text-[4rem] lg:leading-[0.98]">
              Turn lead research into a reviewable outbound system.
            </h1>
            <p className="hf-enter hf-enter-2 max-w-2xl text-balance text-lg font-medium leading-8 text-[rgba(15,23,42,0.70)]">
              Paste a company URL. HussainFlow builds the dossier, fit score,
              contact context, and outreach draft so every send has a visible
              decision trail before approval.
            </p>

            <div
              id="qualify"
              className="hf-enter hf-enter-3 max-w-2xl rounded-2xl border border-border bg-card/90 p-5 shadow-xl shadow-primary/[0.06] backdrop-blur"
            >
              <QualifyForm />
              <div className="mt-4 flex flex-wrap gap-x-3 gap-y-1 text-sm leading-6 text-muted-foreground">
                <span>Sources included</span>
                <span aria-hidden>/</span>
                <span>Human approval required</span>
                <span aria-hidden>/</span>
                <span>Nothing sends automatically</span>
              </div>
            </div>

            <div className="hf-enter hf-enter-4 hidden max-w-xl items-start justify-between gap-4 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:flex">
              {["Research", "Evaluate", "Review"].map((label, index) => (
                <div key={label} className="relative flex flex-1 flex-col items-center gap-2">
                  {index > 0 && (
                    <span
                      className="absolute right-1/2 top-[13px] h-px w-full bg-primary/35"
                      aria-hidden
                    />
                  )}
                  <span className="relative z-10 inline-flex h-7 w-7 items-center justify-center rounded-full border border-primary/25 bg-primary/10 text-[11px] font-bold text-primary shadow-sm shadow-primary/10">
                    {index + 1}
                  </span>
                  <span className="text-center text-[11px] text-foreground">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <aside className="hf-console-enter hf-console-mockup group/console console-shadow overflow-hidden rounded-2xl border border-border bg-card">
            <div className="relative isolate overflow-hidden border-b border-border bg-secondary/60 px-5 py-4">
              <div className="absolute inset-x-0 top-0 h-px bg-primary/30" aria-hidden />
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <span className="hf-live-dot h-2.5 w-2.5 rounded-full bg-primary shadow-[0_0_0_4px_hsl(var(--primary)/0.25)]" />
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Lead review console
                  </span>
                </div>
                <span className="hf-live-badge rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
                  Review ready
                </span>
              </div>

              <div className="mt-5 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Qualification score</p>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-5xl font-semibold tracking-tight text-foreground">8.4</span>
                    <span className="text-sm font-semibold text-muted-foreground">/ 10</span>
                  </div>
                </div>
                <div className="hf-decision-card rounded-xl border border-border bg-card/85 px-4 py-3 text-right shadow-sm shadow-black/[0.02]">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    Decision
                  </p>
                  <p className="mt-1 text-sm font-semibold text-foreground">
                    Hold for approval
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4 p-5">
              <div className="rounded-2xl border border-border bg-background/70 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Review trail
                  </p>
                  <span className="text-xs font-semibold text-primary">Ready for review</span>
                </div>

                <div className="h-1.5 overflow-hidden rounded-full bg-border">
                  <span className="hf-review-progress block h-full rounded-full bg-primary" />
                </div>

                <div className="mt-4 space-y-3">
                  {CONSOLE_STAGES.map((stage) => (
                    <div key={stage.label} className="hf-workflow-row grid grid-cols-[26px_1fr] items-start gap-3">
                      <span className="hf-review-step-icon mt-0.5 flex h-5 w-5 items-center justify-center rounded-full text-success">
                        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                      </span>
                      <div className="min-w-0 sm:flex sm:items-baseline sm:justify-between sm:gap-4">
                        <p className="hf-workflow-label text-sm font-semibold text-foreground">
                          {stage.label}
                        </p>
                        <p className="hf-workflow-detail mt-0.5 text-[13px] text-muted-foreground sm:mt-0 sm:text-right">
                          {stage.detail}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="hf-approval-card group/approval grid grid-cols-[1fr_auto] items-center gap-4 rounded-2xl border border-primary/20 bg-primary/5 p-4 transition-all duration-300 hover:border-primary/35 hover:bg-primary/[0.08] hover:shadow-sm hover:shadow-primary/10">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-primary transition-transform duration-300 group-hover/approval:scale-110" aria-hidden />
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      Nothing sends without approval.
                    </p>
                    <p className="mt-1 text-[13px] leading-5 text-slate-600">
                      The draft waits for review before any email can leave the system.
                    </p>
                  </div>
                </div>
                <ArrowRight className="hf-approval-arrow hidden h-4 w-4 text-primary transition-transform duration-300 group-hover/approval:translate-x-1.5 sm:block" aria-hidden />
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-16 sm:py-20">
        <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            How it works
            </p>
            <h2 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              From company URL to reviewed outreach.
            </h2>
          </div>
          <Link
            href="#qualify"
            className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:text-foreground"
          >
            Start a research run
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>

        <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="group relative flex flex-col gap-5 rounded-2xl border border-border bg-card/80 p-6 shadow-sm shadow-black/[0.02] transition-colors duration-200 hover:border-primary/25 hover:bg-card"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/15 transition-colors group-hover:bg-primary/15">
                <step.icon className="h-5 w-5" aria-hidden />
              </div>
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
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

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span
              aria-hidden
              className="mt-1 inline-block h-3 w-3 rounded-full bg-primary shadow-[0_0_0_5px_hsl(var(--primary)/0.12)]"
            />
            <div className="space-y-1">
              <span className="block font-semibold tracking-tight text-foreground">
                Outbound Lead Agent
              </span>
              <span className="block text-xs leading-relaxed text-muted-foreground">
                Lead research, fit signals, outreach draft, and approval before send
              </span>
            </div>
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
