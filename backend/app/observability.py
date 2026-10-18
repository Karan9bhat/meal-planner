"""Sentry tracing for the backend (no-op without SENTRY_DSN).

- FastAPI requests become transactions (auto-enabled by the SDK).
- Every model call through the OpenAI client becomes a gen_ai span with model, latency and token usage.
- The planner and the region knowledge writer are wrapped in agent spans so a plan reads as one agent run.
Prompt and response text is never sent (it contains users' answers): only models, timings, tokens and errors.
"""

import os
from contextlib import contextmanager

import sentry_sdk

_enabled = False


def init() -> bool:
    global _enabled
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    from sentry_sdk.integrations.openai import OpenAIIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        send_default_pii=False,
        integrations=[OpenAIIntegration(include_prompts=False)],
    )
    sentry_sdk.set_tag("service", "backend")
    _enabled = True
    return True


@contextmanager
def agent_span(agent: str, **data):
    """An invoke_agent span (Sentry's AI agent view groups model calls and tools under it)."""
    if not _enabled:
        yield None
        return
    with sentry_sdk.start_span(op="gen_ai.invoke_agent", name=f"invoke_agent {agent}") as span:
        span.set_data("gen_ai.operation.name", "invoke_agent")
        span.set_data("gen_ai.agent.name", agent)
        for k, v in data.items():
            span.set_data(k, v)
        yield span


@contextmanager
def step_span(name: str, **data):
    if not _enabled:
        yield None
        return
    with sentry_sdk.start_span(op="function", name=name) as span:
        for k, v in data.items():
            span.set_data(k, v)
        yield span
