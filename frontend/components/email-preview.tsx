import { Mail } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

type Props = {
  subject: string | null;
  body: string | null;
  recipientEmail?: string | null;
};

export function EmailPreview({ subject, body, recipientEmail }: Props) {
  if (!subject && !body) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">
          No email draft available.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="space-y-3 pb-4">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Mail className="h-3.5 w-3.5" aria-hidden />
          Drafted email
        </div>
        <div className="space-y-2 text-sm">
          {recipientEmail && (
            <div className="flex gap-3">
              <span className="w-16 shrink-0 text-muted-foreground">To:</span>
              <span className="text-foreground">{recipientEmail}</span>
            </div>
          )}
          <div className="flex gap-3">
            <span className="w-16 shrink-0 text-muted-foreground">Subject:</span>
            <span className="font-medium text-foreground">{subject ?? "(no subject)"}</span>
          </div>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {body ?? "(no body)"}
        </div>
      </CardContent>
    </Card>
  );
}
