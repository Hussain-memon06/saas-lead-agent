/** @type {import('next').NextConfig} */
const nextConfig = {
  // In dev, proxy /api/* to the FastAPI backend on :8080 so the browser
  // sees a single origin and we avoid adding CORS middleware on the
  // backend.  Disabled when NEXT_PUBLIC_API_BASE_URL is set (prod build),
  // because in that case the client calls the absolute URL directly.
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_BASE_URL) {
      return [];
    }
    const target = process.env.BACKEND_PROXY_TARGET || "http://localhost:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },
  // /api/qualify takes 60-90 s to return (sequential research chain).
  // Next's default upstream proxy timeout is 30 s, which surfaces as
  // ECONNRESET in the browser long before the backend finishes. Bump
  // it to 120 s so the proxy waits as long as our client-side
  // AbortController does.
  experimental: {
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
