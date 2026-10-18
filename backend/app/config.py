"""Runtime settings and model routing. Secrets are only ever read from the environment / .env."""

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

# Project-root .env first, then an optional backend/.env override.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


# ---------- providers ----------

@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str = field(repr=False)  # keep keys out of logs / reprs
    output_headroom: float = 1.0  # multiplier on max_tokens for models that think inline
    # Gemma 4 on AI Studio always thinks and the API can't turn it off, but a one-line
    # instruction cuts an outline call from ~80 s to ~25 s.
    brief_thinking: bool = False
    # Slow hosts (~40 tok/s) get the week split into small parallel calls instead of one big one.
    chunked: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


# Every provider serves open-weight models behind an OpenAI-compatible API,
# so hosted (Groq, Google AI Studio) and fully local (Ollama) are interchangeable.
PROVIDERS = {
    "groq": Provider("groq", "https://api.groq.com/openai/v1", _env("GROQ_API_KEY", "API_KEY")),
    "google": Provider(
        "google",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        _env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMMA_API_KEY"),
        output_headroom=1.5,
        brief_thinking=True,
        chunked=True,
    ),
    "ollama": Provider("ollama", _env("OLLAMA_BASE_URL", default="http://localhost:11434/v1"), "ollama", chunked=True),
}


# ---------- models ----------

@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    provider: str
    model: str


MODELS = {
    m.id: m
    for m in [
        ModelSpec("gpt-oss-120b", "gpt-oss-120b", "groq", _env("GROQ_MODEL", default="openai/gpt-oss-120b")),
        ModelSpec("qwen-27b", "Qwen 3.8 27B", "groq", _env("GROQ_FAST_MODEL", default="qwen/qwen3.8-27b")),
        ModelSpec("gemma-4-26b", "Gemma 4 26B-A4B", "google", _env("GEMMA_MODEL", default="gemma-4-26b-a4b-it")),
        ModelSpec("gemma-4-31b", "Gemma 4 31B", "google", _env("GEMMA_LARGE_MODEL", default="gemma-4-31b-it")),
        ModelSpec("gemma-local", "Gemma (local)", "ollama", _env("OLLAMA_MODEL", default="gemma3:1b")),
    ]
}


# ---------- routing ----------
# The user never picks a model: each task has an ordered chain, adjusted by what the input looks like.
# Later entries are fallbacks for rate limits, overload and timeouts.

ROUTES = {
    # Long structured output: needs the fastest strong model; Gemma (chunked) as last resort.
    "plan": (["gpt-oss-120b", "qwen-27b", "gemma-4-26b", "gemma-4-31b"], "long structured plan → fastest strong model"),
    # Short extraction (location → country/cuisine): fast, no reasoning needed.
    "extract": (["qwen-27b", "gpt-oss-120b", "gemma-4-26b"], "short extraction → fast model"),
    # Writing a cuisine profile for the knowledge base: broad world knowledge; runs once per region, then cached.
    "knowledge": (["gemma-4-26b", "gemma-4-31b", "gpt-oss-120b"], "world food knowledge, cached after one run → Gemma 4"),
}

_NON_LATIN = re.compile(r"[Ѐ-ӿ؀-ۿऀ-෿฀-๿぀-ヿ㐀-鿿가-힯]")
LOCAL_ONLY = _env("LOCAL_ONLY", default="false").lower() == "true"
ENABLE_LOCAL_MODELS = _env("ENABLE_LOCAL_MODELS", default="true").lower() == "true"


@dataclass(frozen=True)
class Route:
    task: str
    models: list[ModelSpec]
    reason: str


_ollama_cache: tuple[float, set[str]] = (0.0, set())


def _ollama_models() -> set[str]:
    """Models pulled into the local Ollama, cached briefly; empty if Ollama isn't running."""
    global _ollama_cache
    checked, names = _ollama_cache
    if time.monotonic() - checked < 30:
        return names
    url = PROVIDERS["ollama"].base_url.removesuffix("/v1").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            names = {m["name"] for m in json.load(resp).get("models", [])}
    except (OSError, ValueError):
        names = set()
    _ollama_cache = (time.monotonic(), names)
    return names


def _usable(m: ModelSpec) -> bool:
    if m.provider == "ollama":
        return ENABLE_LOCAL_MODELS and m.model in _ollama_models()
    return PROVIDERS[m.provider].configured and not LOCAL_ONLY


def _parse_overrides(raw: str) -> dict[str, list[str]]:
    """ROUTE_OVERRIDE="plan=gemma-4-26b,gemma-4-31b;extract=gemma-4-26b" pins a task to specific models (testing)."""
    out: dict[str, list[str]] = {}
    for part in filter(None, (p.strip() for p in raw.split(";"))):
        task, _, ids = part.partition("=")
        out[task.strip()] = [i.strip() for i in ids.split(",") if i.strip() in MODELS]
    return out


ROUTE_OVERRIDES = _parse_overrides(_env("ROUTE_OVERRIDE"))


def route(task: str, text: str = "") -> Route:
    if ROUTE_OVERRIDES.get(task):
        ids = ROUTE_OVERRIDES[task]
        return Route(task, [MODELS[i] for i in ids if _usable(MODELS[i])], f"pinned by ROUTE_OVERRIDE → {', '.join(ids)}")
    ids, reason = ROUTES[task]
    ids = list(ids)
    if task == "extract" and _NON_LATIN.search(text):
        ids.remove("gemma-4-26b")
        ids.insert(0, "gemma-4-26b")
        reason = "non-Latin script → Gemma 4 (trained on 140+ languages)"
    if LOCAL_ONLY:
        ids, reason = ["gemma-local"], "local-only mode → Gemma on this machine"
    models = [MODELS[i] for i in ids if _usable(MODELS[i])]
    return Route(task, models, reason)


def models_status() -> list[dict]:
    return [{"id": m.id, "label": m.label, "provider": m.provider, "model": m.model, "available": _usable(m)} for m in MODELS.values()]


CORS_ORIGINS = [
    o.strip() for o in _env("CORS_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()
]
# Any localhost port in dev (Next.js hops to 3001+ when 3000 is busy). Set to "" to disable.
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"^http://(localhost|127\.0\.0\.1)(:\d+)?$") or None
