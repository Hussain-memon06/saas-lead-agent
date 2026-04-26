import { Search, Users, Mail, ShieldCheck } from "lucide-react";
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

export default function HomePage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 sm:py-24">
      <section className="space-y-8">
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            AI SDR Agent
          </p>
          <h1 className="text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            AI-powered B2B lead research, with a human in the loop.
          </h1>
          <p className="text-balance text-lg text-muted-foreground">
            Paste a company URL. Get a one-page dossier, a fit score, and a
            personalised outreach email — ready for your approval before send.
          </p>
        </div>

        <QualifyForm />
      </section>

      <section className="mt-20">
        <h2 className="mb-6 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          How it works
        </h2>
        <ol className="grid gap-6 sm:grid-cols-2">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="flex gap-4 rounded-lg border border-border/60 bg-card p-5"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <step.icon className="h-5 w-5" aria-hidden />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">
                  <span className="mr-2 text-muted-foreground">{i + 1}.</span>
                  {step.title}
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <footer className="mt-20 border-t border-border/60 pt-6 text-xs text-muted-foreground">
        <p>
          Built with LangGraph, FastAPI, Next.js, Tailwind &amp; shadcn/ui.
          Open-source on GitHub.
        </p>
      </footer>
    </div>
  );
}
