"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Root QueryClientProvider wired into app/layout.tsx.
 *
 * Mutations are the dominant pattern here (qualify, approve, reject), so
 * defaults are tuned for that:
 * - retries off — a 422 / 500 from the graph is a real error, not a flake
 * - long staleTime so any background queries we add later don't refetch
 *   while the user is mid-flow
 */
function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    // Server: always create a fresh client so requests don't share state
    return makeQueryClient();
  }
  // Browser: singleton — one client per tab
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
