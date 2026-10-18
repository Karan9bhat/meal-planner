import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import graph, kb, region
from . import observability
from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS, models_status
from .llm import LLMError
from .nutrition import compute_targets
from .planner import generate_plan, recheck
from .schemas import Basics, CheckRequest, DayCheck, PlanResponse, Profile, Targets

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# Before the app is created, so Sentry's FastAPI integration instruments it.
if observability.init():
    logging.getLogger("mealplanner").info("Sentry tracing enabled")


def _sync_graph() -> None:
    if graph.seed():
        # Profiles generated while Atlas was unreachable exist only as local files: push them up (idempotent).
        for p in list(kb.CUISINES.values()):
            if p.source != "curated":
                graph.save_cuisine(p)
        added = kb.merge_graph_cuisines()
        logging.getLogger("mealplanner").info("knowledge graph ready (%d generated cuisines loaded)", added)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # In the background so a slow or missing Atlas never delays startup; the JSON knowledge base serves meanwhile.
    threading.Thread(target=_sync_graph, daemon=True).start()
    yield


app = FastAPI(title="meal-planner API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    """This is the API, not the website; say so instead of a bare 404 (also answers Render's HEAD / probe)."""
    return {
        "service": "meal-planner API",
        "website": os.getenv("PUBLIC_APP_URL", "https://kilobite-planner-web.onrender.com"),
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"ok": True, "models": models_status(), "cuisines": len(kb.CUISINES), "graph": graph.available()}


@app.get("/api/graph/stats")
def graph_stats():
    return graph.stats()


class ExplainRequest(BaseModel):
    cuisine_key: str
    diet_type: str = "omnivore"
    restrictions: list[str] = []
    allergies: list[str] = []


@app.post("/api/graph/explain")
def graph_explain(req: ExplainRequest):
    """Which dishes of a cuisine these preferences allow, and which rule blocks the rest."""
    if req.cuisine_key not in kb.CUISINES:
        raise HTTPException(404, "Unknown cuisine")
    return graph.explain(req.cuisine_key, req.diet_type, req.restrictions, req.allergies)


@app.get("/api/options")
def options():
    return kb.options_payload()


@app.post("/api/targets", response_model=Targets)
def targets(basics: Basics):
    return compute_targets(basics)


class LocationRequest(BaseModel):
    location: str = Field(min_length=2, max_length=120)


# Plain `def` endpoints run in FastAPI's threadpool, so blocking model calls don't stall the server.
@app.post("/api/region/resolve", response_model=region.Resolution)
def resolve_region(req: LocationRequest):
    return region.resolve(req.location)


@app.get("/api/region/{key}", response_model=region.Resolution)
def region_status(key: str):
    res = region.status(key)
    if res is None:
        raise HTTPException(404, "Unknown region")
    return res


class LookupRequest(BaseModel):
    text: str = Field(max_length=4000)
    region_keys: list[str] = []
    diet_type: str = "omnivore"
    restrictions: list[str] = []
    allergies: list[str] = []
    mode: str = "mentioned"  # "mentioned": dishes named in free text; "search": query search
    limit: int = Field(default=20, le=40)


@app.post("/api/kb/lookup")
def kb_lookup(req: LookupRequest):
    """Knowledge-base grounding for the agents: nutrition for dishes in the user's text or a search query."""
    keys = [k for k in req.region_keys if k in kb.CUISINES]
    if req.mode == "search":
        banned = kb.excluded_tags(req.diet_type, req.restrictions, req.allergies)
        return {"dishes": kb.search_dishes(req.text, prefer=keys, banned=banned, limit=req.limit)}
    profiles = [kb.CUISINES[k] for k in keys]
    return {
        "dishes": kb.mentioned_dishes(req.text, keys, limit=req.limit),
        "pantry_basics": sorted({p for c in profiles for p in c.pantry_basics}),
        "meal_times": profiles[0].meal_times if profiles else {},
    }


@app.post("/api/plan", response_model=PlanResponse)
def plan(profile: Profile):
    return generate_plan(profile)


@app.post("/api/plan/check", response_model=list[DayCheck])
def plan_check(req: CheckRequest):
    return recheck(req)
