// Runtime config for the browser: where the FastAPI backend lives. Read on every request (not baked in at build
// time), so moving the backend only needs BACKEND_URL changed on the web service, not a rebuild.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET(req: Request) {
  const apiUrl = (process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  // A common deploy slip: pointing BACKEND_URL at this website instead of the Python API service.
  const self = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? "";
  let problem: string | null = null;
  try {
    if (self && new URL(apiUrl).host === self) {
      problem = "BACKEND_URL points to this website itself. Set it to the URL of the Python API service (the one running uvicorn).";
    }
  } catch {
    problem = `BACKEND_URL is not a valid URL: ${apiUrl}`;
  }
  return Response.json({ apiUrl, problem });
}
