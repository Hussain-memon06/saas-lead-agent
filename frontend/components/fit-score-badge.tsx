import { cn } from "@/lib/utils";

type Props = {
  score: number | null;
  className?: string;
};

/**
 * 1–10 fit-score visualisation: number on the left, 10-segment bar on the
 * right.  Colour shifts from muted (low) → primary (mid) → success (high)
 * to give an at-a-glance read.
 */
export function FitScoreBadge({ score, className }: Props) {
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

  return (
    <div className={cn("flex items-center gap-4", className)}>
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
  );
}
