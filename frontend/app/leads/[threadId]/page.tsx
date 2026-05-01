"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle } from "lucide-react";

import type { QualifyResponse } from "@/lib/types";
import { useIcp } from "@/lib/icp";
import { Button } from "@/components/ui/button";
import { DossierCard } from "@/components/dossier-card";
import { ContactCard } from "@/components/contact-card";
import { SignalsList } from "@/components/signals-list";
import { FitScoreBadge } from "@/components/fit-score-badge";
import { EmailPreview } from "@/components/email-preview";
import { ErrorBanner } from "@/components/error-banner";
import { DecisionButtons } from "@/components/decision-buttons";

export default function LeadPage() {
  const params = useParams<{ threadId: string }>();
  const threadId = decodeURIComponent(params.threadId);
  const { configured: icpConfigured } = useIcp();

  // Read the cache seeded by the qualify form.  Direct loads / hard refreshes
  // hit this with no cached data — we render an empty state in that case.
  const { data } = useQuery<QualifyResponse | undefined>({
    queryKey: ["lead", threadId],
    queryFn: () => undefined, // no fetcher; we only consume cached data
    enabled: false,
    staleTime: Infinity,
  });

  if (!data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back home
        </Link>
        <div className="mt-8 space-y-3 rounded-lg border border-border/60 bg-card p-8 text-center">
          <h1 className="text-lg font-semibold text-foreground">
            No dossier data
          </h1>
          <p className="text-sm text-muted-foreground">
            Dossiers are held in browser memory between qualify runs. Run a
            new search to view a fresh report.
          </p>
          <div className="pt-2">
            <Button asChild>
              <Link href="/">Start a new research</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const errored = data.errors.length > 0 && !data.interrupted;

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-12">
      {/* Header */}
      <div className="space-y-3">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          New search
        </Link>
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Dossier
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">
              {data.company_profile?.name ?? threadId.replace(/^lead:/, "")}
            </h1>
          </div>
        </div>
      </div>

      {errored && (
        <ErrorBanner
          title="Pipeline reported errors"
          message="The graph completed without pausing for approval. Review the messages below."
          details={data.errors}
        />
      )}

      {/* ICP-not-set warning — only when the user hasn't configured one. */}
      {!icpConfigured && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4"
        >
          <AlertTriangle
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-600"
            aria-hidden
          />
          <div className="min-w-0 flex-1 space-y-1 text-sm">
            <p className="font-medium text-foreground">
              You haven&apos;t set your ICP yet
            </p>
            <p className="text-muted-foreground">
              <Link
                href="/settings"
                className="font-medium text-amber-700 underline-offset-2 hover:underline"
              >
                Configure now →
              </Link>{" "}
              for a score tailored to your targets.
            </p>
          </div>
        </div>
      )}

      {/* Fit score — full-width strip */}
      <section className="rounded-lg border border-border/60 bg-card p-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Fit score
        </p>
        <FitScoreBadge
          score={data.fit_score}
          explanation={data.score_explanation}
        />
      </section>

      {/* Two-column on desktop: dossier + (contact stack) */}
      <div className="grid gap-6 lg:grid-cols-2">
        <DossierCard profile={data.company_profile} />
        <div className="space-y-6">
          <ContactCard contact={data.contact} />
          <SignalsList signals={data.signals} />
        </div>
      </div>

      {/* Email draft + decision gate — full width */}
      <div className="space-y-4">
        <EmailPreview
          subject={data.email_subject}
          body={data.email_body}
          recipientEmail={data.contact?.email}
        />
        {(data.interrupted || data.send_result) && (
          <DecisionButtons threadId={threadId} state={data} />
        )}
      </div>

      {data.errors.length > 0 && data.interrupted && (
        <ErrorBanner
          title="Non-fatal errors during research"
          message="Some research steps reported errors but the pipeline produced a draft. Review before approving."
          details={data.errors}
        />
      )}
    </div>
  );
}
