"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const STEPS = [
  { label: "Identifying the company", duration: 8 },
  { label: "Reviewing positioning and fit signals", duration: 18 },
  { label: "Looking for decision-makers", duration: 14 },
  { label: "Preparing the review and outreach draft", duration: 12 },
] as const;

/**
 * Decorative progress for the long qualify call.  Steps advance on a fixed
 * schedule that roughly tracks the backend pipeline — they're a UX cue, not
 * a real progress feed.  If the request finishes faster, the parent unmounts
 * us; if slower, the last step keeps spinning.
 */
export function LoadingState({ url }: { url: string }) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    let elapsed = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let i = 0; i < STEPS.length - 1; i++) {
      elapsed += STEPS[i].duration;
      timers.push(
        setTimeout(() => setActive((cur) => Math.max(cur, i + 1)), elapsed * 1000),
      );
    }
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <Card className="space-y-6 rounded-2xl border-border bg-card/95 p-6 shadow-sm shadow-black/[0.02] sm:p-8">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          Building dossier
        </p>
        <p className="break-all text-base font-semibold text-foreground">{url}</p>
        <p className="text-sm text-muted-foreground">
          This usually takes 60–90 seconds. Keep this tab open.
        </p>
      </div>

      <ol className="space-y-3" aria-live="polite">
        {STEPS.map((step, i) => {
          const state = i < active ? "done" : i === active ? "active" : "pending";
          return (
            <li
              key={step.label}
              className="flex items-center gap-3 text-sm"
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                {state === "done" && (
                  <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
                )}
                {state === "active" && (
                  <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden />
                )}
                {state === "pending" && (
                  <span className="h-2 w-2 rounded-full bg-muted-foreground/30" aria-hidden />
                )}
              </span>
              <span
                className={
                  state === "pending"
                    ? "text-muted-foreground/60"
                    : state === "done"
                      ? "text-muted-foreground"
                      : "font-medium text-foreground"
                }
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="space-y-2 pt-2">
        <Skeleton className="h-4 w-3/5" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-2/5" />
      </div>
    </Card>
  );
}
