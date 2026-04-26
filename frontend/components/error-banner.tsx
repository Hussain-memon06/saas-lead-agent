import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  title?: string;
  message: string;
  details?: string[];
  onRetry?: () => void;
};

export function ErrorBanner({ title = "Something went wrong", message, details, onRetry }: Props) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className="rounded-lg border border-destructive/30 bg-destructive/5 p-4"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="text-sm text-muted-foreground">{message}</p>
          {details && details.length > 0 && (
            <ul className="ml-4 list-disc space-y-0.5 text-xs text-muted-foreground">
              {details.slice(0, 5).map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
          {onRetry && (
            <div className="pt-1">
              <Button size="sm" variant="outline" onClick={onRetry}>
                Try again
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
