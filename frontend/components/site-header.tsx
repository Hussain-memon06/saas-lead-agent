"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Settings } from "lucide-react";

import { useIcp } from "@/lib/icp";

const REPO_URL = "https://github.com/Hussain-memon06/saas-lead-agent";

/**
 * Inline GitHub mark — lucide-react v1 dropped brand icons for trademark
 * reasons.  Permitted use under GitHub's logo guidelines: "link to GitHub".
 * https://github.com/logos
 */
function GithubMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
      className={className}
    >
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.27-.01-1-.02-1.96-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.07 11.07 0 0 1 5.79 0c2.21-1.49 3.18-1.18 3.18-1.18.62 1.59.23 2.76.11 3.05.74.81 1.18 1.84 1.18 3.1 0 4.42-2.69 5.39-5.26 5.68.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.15 0 .31.21.68.8.56A10.51 10.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
    </svg>
  );
}

function IcpStatusBadge() {
  const [mounted, setMounted] = useState(false);
  const { configured } = useIcp();

  useEffect(() => {
    setMounted(true);
  }, []);

  // The badge depends on localStorage (read inside useIcp), which doesn't
  // exist during SSR.  Returning null on both the server render and the
  // first client render keeps the markup identical, then the badge mounts
  // after hydration and reflects the real value.
  if (!mounted) return null;

  if (configured) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        ICP configured
      </span>
    );
  }
  return (
    <Link
      href="/settings"
      className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-500/15"
    >
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
      Set your ICP
    </Link>
  );
}

export function SiteHeader() {
  return (
    <header
      aria-label="Site header"
      className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link
          href="/"
          className="flex items-center gap-2 tracking-tight"
        >
          <span
            aria-hidden
            className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-sm font-bold text-white"
          >
            D
          </span>
          <span className="text-lg font-semibold text-gray-900">Dossify</span>
        </Link>
        <div className="flex items-center gap-3">
          <IcpStatusBadge />
          <Link
            href="/settings"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <Settings className="h-4 w-4" aria-hidden />
            Settings
          </Link>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <GithubMark className="h-4 w-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </div>
    </header>
  );
}
