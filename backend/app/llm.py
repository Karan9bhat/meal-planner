"""JSON chat over any OpenAI-compatible endpoint (Groq, Google AI Studio, Ollama), with cross-provider fallback."""

import json
import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from .config import PROVIDERS, ModelSpec, Provider, Route

log = logging.getLogger("mealplanner.llm")

MAX_RATE_LIMIT_WAIT_S = 25


class LLMError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


@dataclass
class LLMResult:
    data: dict
    model: ModelSpec  # the model that actually answered (may be a fallback)
    reason: str  # why the router picked this chain


@lru_cache(maxsize=None)
def _client(provider_name: str) -> OpenAI:
    p = PROVIDERS[provider_name]
    # Local CPU inference and Google's free Gemma (~40 tok/s) are slow; give them room.
    timeout = {"ollama": 600, "google": 240}.get(provider_name, 120)
    return OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=timeout, max_retries=0)


# Reasoning that some models (Qwen <think>, Gemma 4 <thought>) put inline before the answer.
_THINK = re.compile(r"<(think|thought)>.*?</\1>", re.DOTALL)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _json_values(text: str) -> list:
    """Every top-level JSON value in text, skipping prose between them."""
    decoder, values, i = json.JSONDecoder(), [], 0
    while (i := min((j for j in (text.find("{", i), text.find("[", i)) if j != -1), default=-1)) != -1:
        try:
            value, i = decoder.raw_decode(text, i)
            values.append(value)
        except json.JSONDecodeError:
            i += 1
    return values


def _parse_json(text: str) -> dict:
    text = _FENCE.sub("", _THINK.sub("", text).strip())
    try:
        values = [json.loads(text)]
    except json.JSONDecodeError:
        # Models without a JSON mode wrap objects in prose, or emit several objects back to back
        # (Gemma sometimes splits {"days": [...]} into one object per day).
        values = _json_values(text)
    objects: list[dict] = []
    for v in values:
        # Gemma also sometimes wraps the object in an array.
        objects += [x for x in v if isinstance(x, dict)] if isinstance(v, list) else [v] if isinstance(v, dict) else []
    if not objects:
        raise json.JSONDecodeError("expected a JSON object", text, 0)
    merged = dict(objects[0])
    for extra in objects[1:]:
        for key, value in extra.items():
            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = merged[key] + value
            else:
                merged.setdefault(key, value)
    return merged


# Compact JSON matters at ~40 tok/s: indentation alone is ~1/3 of the tokens.
BRIEF_THINKING = (
    "\nThink only briefly (at most 5 short lines) before answering, then output compact JSON on a single line"
    " with no indentation."
)


def _messages(p: Provider, system: str, user: str) -> list[dict]:
    if p.brief_thinking:
        system += BRIEF_THINKING
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _model_options(p: Provider, model: str) -> dict:
    opts: dict = {"response_format": {"type": "json_object"}}
    # Reasoning models spend output tokens thinking; keep that small to stay inside free-tier limits.
    if "gpt-oss" in model:
        opts["reasoning_effort"] = "low"
    elif p.name == "groq" and "qwen3" in model:
        opts["reasoning_effort"] = "none"
    return opts


def _retry_after(e: RateLimitError) -> float | None:
    try:
        return float(e.response.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


def _complete_json(spec: ModelSpec, system: str, user: str, budget: int, temperature: float) -> dict:
    """One completion parsed as JSON. If the output was cut off, retry once with double the room
    (thinking models occasionally ignore the brevity hint). Provider errors propagate to the caller."""
    p = PROVIDERS[spec.provider]
    messages = _messages(p, system, user)
    budget = int(budget * p.output_headroom)
    for room in (budget, budget * 2):
        resp = _client(p.name).chat.completions.create(
            model=spec.model,
            messages=messages,
            temperature=temperature,
            max_tokens=room,
            **_model_options(p, spec.model),
        )
        cut_off = resp.choices[0].finish_reason == "length"
        try:
            return _parse_json(resp.choices[0].message.content or "")
        except json.JSONDecodeError as e:
            if cut_off and room == budget:
                log.warning("%s ran out of room at %d tokens; retrying with more", spec.model, room)
                continue
            if cut_off:
                raise LLMError("The model ran out of room writing its answer.", 502) from e
            raise LLMError("The model returned malformed JSON.", 502) from e
    raise AssertionError("unreachable")


def chat_json(system: str, user: str, *, route: Route, max_tokens: int = 8000, temperature: float = 0.4) -> LLMResult:
    """Tries the route's models in order across providers; waits once if every model is briefly rate-limited."""
    if not route.models:
        raise LLMError("No model is configured for this task. Add an API key to .env (see .env.example).", 500)
    waits: list[float] = []
    last_error: LLMError | None = None

    for attempt in range(2):
        for spec in route.models:
            try:
                data = _complete_json(spec, system, user, max_tokens, temperature)
            except RateLimitError as e:
                wait = _retry_after(e)
                log.warning("rate limited on %s (retry-after=%s)", spec.model, wait)
                if wait is not None:
                    waits.append(wait)
                continue
            except APIStatusError as e:
                # 413 on Groq = request bigger than this model's per-minute budget; 5xx = overloaded host.
                if e.status_code == 413 or e.status_code >= 500:
                    log.warning("%s %s on %s; trying next model", spec.provider, e.status_code, spec.model)
                    last_error = LLMError(f"{spec.label} is overloaded right now. Try again shortly.", 503)
                    continue
                log.warning("%s error on %s: %s", spec.provider, spec.model, e.message)
                raise LLMError(f"Model provider error ({spec.provider} {e.status_code}).", 502) from e
            except APIConnectionError as e:  # includes timeouts
                log.warning("couldn't reach %s for %s: %s", spec.provider, spec.model, e)
                last_error = LLMError(f"Couldn't reach the model provider ({spec.provider}).", 503)
                continue
            except LLMError as e:  # bad JSON from this model: another model may do better
                log.warning("%s: %s", spec.model, e)
                last_error = e
                continue
            return LLMResult(data, spec, route.reason)

        # Every model is rate-limited: wait once if the provider says it's brief.
        shortest = min(waits) if waits else None
        if attempt == 0 and shortest is not None and shortest <= MAX_RATE_LIMIT_WAIT_S:
            time.sleep(shortest + 1)
            waits.clear()
            continue
        break

    if waits:
        raise LLMError(f"The free model tier is busy right now. Try again in ~{int(min(waits))}s.", 429)
    raise last_error or LLMError("No model could answer right now. Try again in a minute.", 503)
