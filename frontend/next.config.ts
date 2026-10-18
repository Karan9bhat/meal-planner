import fs from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

// One .env for the whole project (repo root): the agent routes need the same model keys as the backend.
// Next's own loader only reads frontend/.env*, so fill in anything missing from ../.env without overriding
// values already set in the real environment (e.g. on Render).
function loadRootEnv() {
  const file = path.resolve(process.cwd(), "..", ".env");
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
loadRootEnv();

const nextConfig: NextConfig = {
  // Mastra runs only in server route handlers; keep it out of the bundler.
  serverExternalPackages: ["@mastra/core", "@mastra/ai-sdk", "@mastra/observability", "@mastra/sentry", "@sentry/node"],
};

export default nextConfig;
