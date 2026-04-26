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
};

export default nextConfig;
