import { Mail, User, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Contact } from "@/lib/types";

type Props = { contact: Contact | null };

export function ContactCard({ contact }: Props) {
  if (!contact || !contact.email) {
    return (
      <Card>
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <User className="h-3.5 w-3.5" aria-hidden />
            Contact
          </div>
          <CardTitle className="text-lg">No contact found</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Hunter.io didn&apos;t return a decision-maker email for this domain.
        </CardContent>
      </Card>
    );
  }

  const display = contact.name || contact.email;

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <User className="h-3.5 w-3.5" aria-hidden />
          Contact
        </div>
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-lg">{display}</CardTitle>
          {typeof contact.confidence === "number" && (
            <Badge variant="secondary" className="shrink-0">
              {contact.confidence}% confidence
            </Badge>
          )}
        </div>
        {contact.title && (
          <p className="text-sm text-muted-foreground">{contact.title}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-muted-foreground" aria-hidden />
          <a
            href={`mailto:${contact.email}`}
            className="font-medium text-foreground underline-offset-2 hover:underline"
          >
            {contact.email}
          </a>
        </div>
        {contact.linkedin && (
          <div className="flex items-center gap-2">
            <ExternalLink className="h-4 w-4 text-muted-foreground" aria-hidden />
            <a
              href={contact.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline-offset-2 hover:underline"
            >
              LinkedIn
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
