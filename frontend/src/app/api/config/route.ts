// Runtime config for the browser: where the FastAPI backend lives. Read on every request (not baked in at build
// time), so moving the backend only needs BACKEND_URL changed on the web service, not a rebuild.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET() {
  const apiUrl = (process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  return Response.json({ apiUrl });
}
