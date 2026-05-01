import { cn } from "@/lib/utils";

type Props = {
  score: number | null;
  /** Optional one-line rationale from dossier_writer (e.g.
   *  "7/10 — Industry: B2B SaaS ✅ | Stage: Series C ✅ | …"). */
  explanation?: string | null;
  className?: string;
};

/**
 * 1–10 fit-score visualisation: number on the left, 10-segment bar on the
 * right.  Colour shifts from muted (low) → primary (mid) → success (high)
 * to give an at-a-glance read.  When `explanation` is present, an
 * attribute-by-attribute rationale renders below the bar in monospace.
 */
export function FitScoreBadge({ score, explanation, className }: Props) {
  if (score === null || score === undefined) {
    return (
      <div className={cn("text-sm text-muted-foreground", className)}>
        No fit score
      </div>
    );
  }

  const clamped = Math.max(1, Math.min(10, Math.round(score)));
  const tone =
    clamped >= 8
      ? "text-success"
      : clamped >= 5
        ? "text-primary"
        : "text-muted-foreground";

  // Strip the leading "N/10 — " prefix so it doesn't repeat the big
  // number above; if the model's output doesn't follow the format,
  // render it untouched.
  const trimmedExplanation = explanation
    ? explanation.replace(/^\s*\d+\s*\/\s*10\s*[—–-]\s*/, "").trim()
    : "";

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-1">
          <span className={cn("text-3xl font-semibold tabular-nums", tone)}>
            {clamped}
          </span>
          <span className="text-sm text-muted-foreground">/ 10</span>
        </div>
        <div
          role="meter"
          aria-valuenow={clamped}
          aria-valuemin={1}
          aria-valuemax={10}
          aria-label={`Fit score ${clamped} out of 10`}
          className="flex flex-1 gap-1"
        >
          {Array.from({ length: 10 }).map((_, i) => (
            <span
              key={i}
              className={cn(
                "h-2 flex-1 rounded-sm",
                i < clamped
                  ? clamped >= 8
                    ? "bg-success"
                    : clamped >= 5
                      ? "bg-primary"
                      : "bg-muted-foreground/60"
                  : "bg-muted",
              )}
            />
          ))}
        </div>
      </div>
      {trimmedExplanation && (
        <p className="font-mono text-xs leading-relaxed text-muted-foreground">
          {trimmedExplanation}
        </p>
      )}
    </div>
  );
}
