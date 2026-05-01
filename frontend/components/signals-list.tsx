import { Activity, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Signal } from "@/lib/types";

type Props = { signals: Signal[] | null };

const TYPE_LABELS: Record<string, string> = {
  funding: "Funding",
  hiring: "Hiring",
  product: "Product",
  leadership: "Leadership",
  partnership: "Partnership",
  other: "Signal",
};

/**
 * Tailwind palette per signal type.  Kept in one place so the dossier
 * page reads at a glance — funding pops blue, hiring green, etc.
 */
const TYPE_TONE: Record<string, string> = {
  funding: "bg-blue-500/10 text-blue-700 ring-blue-500/20",
  hiring: "bg-emerald-500/10 text-emerald-700 ring-emerald-500/20",
  product: "bg-purple-500/10 text-purple-700 ring-purple-500/20",
  partnership: "bg-orange-500/10 text-orange-700 ring-orange-500/20",
  leadership: "bg-amber-500/10 text-amber-700 ring-amber-500/20",
  other: "bg-secondary text-secondary-foreground ring-border",
};

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function SignalsList({ signals }: Props) {
  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Activity className="h-3.5 w-3.5" aria-hidden />
          Buying signals
        </div>
        <CardTitle className="text-lg">
          {signals && signals.length > 0
            ? `${signals.length} recent signal${signals.length === 1 ? "" : "s"}`
            : "No recent signals"}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!signals || signals.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing notable in the last few months.
          </p>
        ) : (
          <ul className="space-y-5">
            {signals.map((s, i) => {
              const tone = TYPE_TONE[s.signal_type] ?? TYPE_TONE.other;
              const label = TYPE_LABELS[s.signal_type] ?? s.signal_type;
              return (
                <li key={`${s.source}-${i}`} className="space-y-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${tone}`}
                  >
                    {label}
                  </span>
                  {s.details && (
                    <p className="text-sm leading-relaxed text-foreground">
                      {s.details}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    {s.date && <span>{s.date}</span>}
                    {s.source && (
                      <a
                        href={s.source}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                      >
                        {hostnameOf(s.source)}
                        <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
