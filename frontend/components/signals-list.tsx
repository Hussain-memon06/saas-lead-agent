import { Activity, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Signal } from "@/lib/types";

type Props = { signals: Signal[] | null };

const TYPE_LABELS: Record<string, string> = {
  funding: "Funding",
  hiring: "Hiring",
  product: "Product",
  techstack: "Tech stack",
  leadership: "Leadership",
  partnership: "Partnership",
  other: "Signal",
};

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
          <ul className="space-y-4">
            {signals.map((s, i) => (
              <li key={`${s.title}-${i}`} className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="font-normal">
                    {TYPE_LABELS[s.type] ?? s.type}
                  </Badge>
                  <p className="font-medium text-foreground">{s.title}</p>
                </div>
                {s.summary && (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {s.summary}
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  {s.date && <span>{s.date}</span>}
                  {s.url && (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                    >
                      Source
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
