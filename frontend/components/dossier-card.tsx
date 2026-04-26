import { Building2, MapPin, Users, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CompanyProfile } from "@/lib/types";

type Props = { profile: CompanyProfile | null };

export function DossierCard({ profile }: Props) {
  if (!profile) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Company</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          No company profile returned.
        </CardContent>
      </Card>
    );
  }

  const facts: { icon: typeof Building2; label: string; value: string | null | undefined }[] = [
    { icon: MapPin, label: "HQ", value: profile.hq },
    { icon: TrendingUp, label: "Stage", value: profile.funding_stage },
    { icon: Users, label: "Employees", value: profile.employees_estimate },
  ];

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Building2 className="h-3.5 w-3.5" aria-hidden />
          Company
        </div>
        <CardTitle className="text-2xl">{profile.name}</CardTitle>
        {profile.tagline && (
          <p className="text-sm text-muted-foreground">{profile.tagline}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
          {facts.map((f) =>
            f.value ? (
              <div key={f.label} className="space-y-0.5">
                <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <f.icon className="h-3 w-3" aria-hidden />
                  {f.label}
                </dt>
                <dd className="text-foreground">{f.value}</dd>
              </div>
            ) : null,
          )}
        </dl>

        {profile.products && profile.products.length > 0 && (
          <Section title="Products">
            <ul className="flex flex-wrap gap-1.5">
              {profile.products.map((p) => (
                <li
                  key={p}
                  className="rounded-md border border-border/60 bg-secondary px-2 py-0.5 text-xs text-foreground"
                >
                  {p}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {profile.notable_customers && profile.notable_customers.length > 0 && (
          <Section title="Notable customers">
            <p className="text-sm text-foreground">
              {profile.notable_customers.join(" · ")}
            </p>
          </Section>
        )}

        {profile.sources && profile.sources.length > 0 && (
          <Section title="Sources">
            <ul className="space-y-1 text-xs">
              {profile.sources.slice(0, 5).map((url) => (
                <li key={url} className="truncate">
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      {children}
    </div>
  );
}
