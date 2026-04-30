"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, qualify } from "@/lib/api";
import type { QualifyResponse } from "@/lib/types";
import { LoadingState } from "@/components/loading-state";
import { ErrorBanner } from "@/components/error-banner";

/**
 * Mirrors the backend's `QualifyRequest.validate_url` rule:
 * scheme must be http or https, netloc non-empty.
 */
const formSchema = z.object({
  url: z
    .string()
    .trim()
    .min(1, "Please paste a company URL.")
    .refine((v) => {
      try {
        const u = new URL(v);
        return (u.protocol === "http:" || u.protocol === "https:") && Boolean(u.host);
      } catch {
        return false;
      }
    }, "URL must start with http:// or https:// (e.g. https://stripe.com)."),
});

type FormValues = z.infer<typeof formSchema>;

export function QualifyForm() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { url: "" },
    mode: "onSubmit",
  });

  const submittedUrl = form.watch("url");

  const mutation = useMutation<QualifyResponse, ApiError, FormValues>({
    mutationFn: ({ url }) => qualify({ url }),
    onSuccess: (data) => {
      // Seed the cache so the dossier page reads without a refetch.
      queryClient.setQueryData(["lead", data.thread_id], data);
      router.push(`/leads/${encodeURIComponent(data.thread_id)}`);
    },
  });

  if (mutation.isPending) {
    return <LoadingState url={submittedUrl} />;
  }

  return (
    <form
      onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      className="space-y-4"
      noValidate
    >
      <div className="space-y-2">
        <Label htmlFor="url" className="text-sm font-medium">
          Company URL
        </Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="url"
            type="url"
            placeholder="https://stripe.com"
            autoComplete="off"
            spellCheck={false}
            aria-invalid={Boolean(form.formState.errors.url) || undefined}
            aria-describedby={form.formState.errors.url ? "url-error" : undefined}
            disabled={mutation.isPending}
            className="h-11 sm:flex-1"
            {...form.register("url")}
          />
          <Button
            type="submit"
            size="lg"
            disabled={mutation.isPending}
            className="h-11 sm:w-40"
          >
            Research
            <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
          </Button>
        </div>
        {form.formState.errors.url && (
          <p
            id="url-error"
            role="alert"
            className="text-sm text-destructive"
          >
            {form.formState.errors.url.message}
          </p>
        )}
      </div>

      {mutation.isError && (
        <ErrorBanner
          title={
            mutation.error.status === 422
              ? "Invalid URL"
              : "Research failed"
          }
          message={mutation.error.message}
          details={mutation.error.errors}
          onRetry={() => mutation.reset()}
        />
      )}
    </form>
  );
}
