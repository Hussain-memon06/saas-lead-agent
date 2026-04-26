"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, X, CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError, approve, reject } from "@/lib/api";
import type { ApproveResponse, QualifyResponse, SendResult } from "@/lib/types";

type Props = {
  threadId: string;
  /** Current cached state for this thread; we read+write it. */
  state: QualifyResponse;
};

const OUTCOME_COPY: Record<
  SendResult,
  { tone: "success" | "muted" | "warning" | "destructive"; title: string; body: string }
> = {
  sent: {
    tone: "success",
    title: "Email sent",
    body: "SendGrid accepted the message for delivery.",
  },
  rejected: {
    tone: "muted",
    title: "Email rejected",
    body: "You declined the draft. Nothing was delivered.",
  },
  no_contact: {
    tone: "warning",
    title: "No contact email",
    body: "Hunter.io didn't return an address, so nothing was delivered.",
  },
  failed: {
    tone: "destructive",
    title: "Delivery failed",
    body: "SendGrid rejected the request. See errors below.",
  },
};

export function DecisionButtons({ threadId, state }: Props) {
  const queryClient = useQueryClient();

  function applyResume(data: ApproveResponse) {
    // Merge resume result into the cached qualify response so the page
    // reflects the new send_result / message_id without a refetch.
    queryClient.setQueryData<QualifyResponse>(["lead", threadId], (prev) =>
      prev
        ? {
            ...prev,
            email_approved: data.email_approved,
            send_result: data.send_result,
            message_id: data.message_id,
            sent_at: data.sent_at,
            interrupted: data.interrupted,
            errors: data.errors,
          }
        : prev,
    );
  }

  const approveMutation = useMutation<ApproveResponse, ApiError, void>({
    mutationFn: () => approve(threadId),
    onSuccess: applyResume,
  });

  const rejectMutation = useMutation<ApproveResponse, ApiError, void>({
    mutationFn: () => reject(threadId),
    onSuccess: applyResume,
  });

  const decided = state.send_result !== null;
  const pending = approveMutation.isPending || rejectMutation.isPending;
  const error = approveMutation.error || rejectMutation.error;

  // Show the outcome banner once a decision lands.
  if (decided && state.send_result) {
    return (
      <OutcomeBanner
        outcome={state.send_result}
        messageId={state.message_id}
        sentAt={state.sent_at}
        errors={state.errors}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Button
          size="lg"
          className="h-11 sm:flex-1"
          disabled={pending}
          onClick={() => approveMutation.mutate()}
        >
          {approveMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Check className="mr-2 h-4 w-4" aria-hidden />
          )}
          Approve &amp; send
        </Button>
        <Button
          size="lg"
          variant="outline"
          className="h-11 sm:flex-1"
          disabled={pending}
          onClick={() => rejectMutation.mutate()}
        >
          {rejectMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <X className="mr-2 h-4 w-4" aria-hidden />
          )}
          Reject
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Approving will deliver the drafted email through SendGrid (or record a
        stub success in dev). This is the last gate.
      </p>
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-foreground"
        >
          <p className="font-medium">Resume failed</p>
          <p className="text-muted-foreground">{error.message}</p>
        </div>
      )}
    </div>
  );
}

function OutcomeBanner({
  outcome,
  messageId,
  sentAt,
  errors,
}: {
  outcome: SendResult;
  messageId: string | null;
  sentAt: string | null;
  errors: string[];
}) {
  const copy = OUTCOME_COPY[outcome];

  const palette = {
    success: {
      border: "border-success/30",
      bg: "bg-success/5",
      icon: <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />,
    },
    muted: {
      border: "border-border/60",
      bg: "bg-secondary/50",
      icon: <XCircle className="h-5 w-5 text-muted-foreground" aria-hidden />,
    },
    warning: {
      border: "border-amber-500/30",
      bg: "bg-amber-500/5",
      icon: <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden />,
    },
    destructive: {
      border: "border-destructive/30",
      bg: "bg-destructive/5",
      icon: <XCircle className="h-5 w-5 text-destructive" aria-hidden />,
    },
  }[copy.tone];

  return (
    <div
      role="status"
      aria-live="polite"
      className={`rounded-lg border ${palette.border} ${palette.bg} p-4`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0">{palette.icon}</span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-semibold text-foreground">{copy.title}</p>
          <p className="text-sm text-muted-foreground">{copy.body}</p>
          {(messageId || sentAt) && (
            <dl className="grid grid-cols-1 gap-1 pt-2 text-xs sm:grid-cols-2">
              {messageId && (
                <div className="flex gap-2">
                  <dt className="text-muted-foreground">Message ID:</dt>
                  <dd className="truncate font-mono text-foreground">{messageId}</dd>
                </div>
              )}
              {sentAt && (
                <div className="flex gap-2">
                  <dt className="text-muted-foreground">Sent at:</dt>
                  <dd className="font-mono text-foreground">{sentAt}</dd>
                </div>
              )}
            </dl>
          )}
          {outcome === "failed" && errors.length > 0 && (
            <ul className="ml-4 list-disc space-y-0.5 pt-1 text-xs text-muted-foreground">
              {errors.slice(0, 3).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
