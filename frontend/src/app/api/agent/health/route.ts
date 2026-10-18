// Which settings the agent server can see: names and true/false only, never values.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const has = (...names: string[]) => names.some((n) => Boolean(process.env[n]));

export function GET() {
  return Response.json({
    ok: true,
    env: {
      groq_key: has("GROQ_API_KEY", "API_KEY"),
      gemma_key: has("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMMA_API_KEY"),
      sentry_dsn: has("SENTRY_DSN"),
      backend_url: process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? null,
      service: process.env.RENDER_SERVICE_NAME ?? "local",
      commit: process.env.RENDER_GIT_COMMIT?.slice(0, 7) ?? null,
    },
  });
}
