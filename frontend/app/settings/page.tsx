"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  EMPLOYEE_RANGE_OPTIONS,
  EMPTY_ICP,
  GEOGRAPHY_OPTIONS,
  INDUSTRY_OPTIONS,
  MUST_HAVE_SIGNAL_OPTIONS,
  RED_FLAG_OPTIONS,
  STAGE_OPTIONS,
  clearIcp,
  loadIcp,
  saveIcp,
  type IcpContext,
} from "@/lib/icp";

/* ----- small helpers (page-local UI primitives) -------------------- */

function TagSelector({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: readonly string[];
  value: string[];
  onChange: (next: string[]) => void;
  ariaLabel: string;
}) {
  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  };
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = value.includes(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            aria-pressed={active}
            className={
              "rounded-full px-3.5 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
              (active
                ? "border border-primary/25 bg-primary/10 text-primary"
                : "border border-border bg-card text-foreground hover:border-primary/30 hover:bg-secondary")
            }
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function CheckboxGroup({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: readonly string[];
  value: string[];
  onChange: (next: string[]) => void;
  ariaLabel: string;
}) {
  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  };
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="grid grid-cols-2 gap-2 sm:grid-cols-3"
    >
      {options.map((opt) => {
        const checked = value.includes(opt);
        return (
          <label
            key={opt}
            className={
              "flex cursor-pointer items-center gap-2 rounded-lg border px-3.5 py-2.5 text-sm font-medium transition-colors " +
              (checked
                ? "border-primary/30 bg-primary/5 text-foreground"
                : "border-border bg-card text-foreground hover:bg-secondary")
            }
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(opt)}
              className="h-4 w-4 rounded border-border text-primary focus:ring-2 focus:ring-ring focus:ring-offset-1"
            />
            {opt}
          </label>
        );
      })}
    </div>
  );
}

/* ----- page ------------------------------------------------------- */

export default function SettingsPage() {
  const [icp, setIcp] = useState<IcpContext>(EMPTY_ICP);
  const [mounted, setMounted] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // localStorage is only available in the browser.  Reading it lives in
  // an effect so the SSR markup and the first client render match —
  // we guard render until the effect has run, then swap to the real form.
  useEffect(() => {
    const stored = loadIcp();
    if (stored) setIcp(stored);
    setMounted(true);
  }, []);

  const update = useMemo(
    () =>
      <K extends keyof IcpContext>(key: K) =>
      (val: IcpContext[K]) =>
        setIcp((prev) => ({ ...prev, [key]: val })),
    [],
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    saveIcp(icp);
    setSavedAt(Date.now());
  }

  function handleReset() {
    clearIcp();
    setIcp(EMPTY_ICP);
    setSavedAt(null);
  }

  // Hide the form briefly to avoid a flash of EMPTY_ICP before localStorage
  // has been read on the client, and so the SSR HTML matches the first
  // client render before useEffect populates the saved values.
  if (!mounted) return null;

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10 sm:py-14">
      <div className="rounded-2xl border border-border bg-card/90 p-6 shadow-sm shadow-black/[0.02] sm:p-8">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back home
        </Link>
        <div className="mt-4 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            Settings
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground">
            Configure your ICP
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
            Tell Outbound Lead Agent what your ideal customer looks like. Your settings
            stay on this device — they&apos;re sent with each research request
            so the agent scores against your actual targets.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ---------- Section A ---------- */}
        <section className="space-y-7 rounded-2xl border border-border bg-card/90 p-6 shadow-sm shadow-black/[0.02] sm:p-8">
          <div className="mb-8 space-y-2 border-b border-border pb-6">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Who are you selling to?
            </h2>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              The agent uses these to filter and score prospects.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="seller_name">Your name / company name</Label>
            <Input
              id="seller_name"
              value={icp.seller_name}
              onChange={(e) => update("seller_name")(e.target.value)}
              placeholder="e.g. John at Acme Agency"
              className="h-11 rounded-lg bg-card"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="offering">What you sell</Label>
            <Input
              id="offering"
              value={icp.offering}
              onChange={(e) => update("offering")(e.target.value)}
              placeholder="e.g. B2B sales automation software for SaaS companies"
              className="h-11 rounded-lg bg-card"
            />
          </div>

          <div className="space-y-2">
            <Label>Target industries</Label>
            <TagSelector
              options={INDUSTRY_OPTIONS}
              value={icp.target_industries}
              onChange={update("target_industries")}
              ariaLabel="Target industries"
            />
          </div>

          <div className="space-y-2">
            <Label>Target company stage</Label>
            <CheckboxGroup
              options={STAGE_OPTIONS}
              value={icp.target_stages}
              onChange={update("target_stages")}
              ariaLabel="Target company stage"
            />
          </div>

          <div className="space-y-2">
            <Label>Target geography</Label>
            <CheckboxGroup
              options={GEOGRAPHY_OPTIONS}
              value={icp.target_geographies}
              onChange={update("target_geographies")}
              ariaLabel="Target geography"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="target_employees">Target employee count</Label>
            <select
              id="target_employees"
              value={icp.target_employees}
              onChange={(e) => update("target_employees")(e.target.value)}
              className="flex h-11 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:max-w-xs"
            >
              {EMPLOYEE_RANGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </section>

        {/* ---------- Section B ---------- */}
        <section className="space-y-7 rounded-2xl border border-border bg-card/90 p-6 shadow-sm shadow-black/[0.02] sm:p-8">
          <div className="mb-8 space-y-2 border-b border-border pb-6">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              What makes a great lead?
            </h2>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              The agent rewards must-have signals and penalizes red flags.
            </p>
          </div>

          <div className="space-y-2">
            <Label>Must-have signals</Label>
            <TagSelector
              options={MUST_HAVE_SIGNAL_OPTIONS}
              value={icp.must_have_signals}
              onChange={update("must_have_signals")}
              ariaLabel="Must-have signals"
            />
          </div>

          <div className="space-y-2">
            <Label>Disqualifying signals / red flags</Label>
            <TagSelector
              options={RED_FLAG_OPTIONS}
              value={icp.red_flags}
              onChange={update("red_flags")}
              ariaLabel="Red flags"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="value_proposition">
              Your value proposition for the email
            </Label>
            <Textarea
              id="value_proposition"
              value={icp.value_proposition}
              onChange={(e) => update("value_proposition")(e.target.value)}
              placeholder="e.g. We help B2B SaaS companies automate their outbound so SDRs focus on closing not prospecting. We've helped teams at Linear and Notion book 3x more meetings."
              rows={4}
              className="rounded-lg bg-card"
            />
          </div>
        </section>

        {/* ---------- Actions ---------- */}
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card/90 p-4 shadow-sm shadow-black/[0.02] sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button type="submit" size="lg" className="h-11 rounded-lg sm:px-8">
              Save settings
            </Button>
            <Button
              type="button"
              size="lg"
              variant="outline"
              className="h-11 rounded-lg"
              onClick={handleReset}
            >
              <RotateCcw className="mr-2 h-4 w-4" aria-hidden />
              Reset
            </Button>
          </div>
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Back to research →
          </Link>
        </div>

        {savedAt && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-start gap-3 rounded-2xl border border-success/20 bg-success/5 p-4"
          >
            <CheckCircle2
              className="mt-0.5 h-5 w-5 shrink-0 text-success"
              aria-hidden
            />
            <div className="space-y-0.5 text-sm">
              <p className="font-medium text-foreground">Your ICP is saved</p>
              <p className="text-muted-foreground">
                Research will now score against your criteria.
              </p>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
