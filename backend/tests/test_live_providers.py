"""Live: every configured model on every provider answers in our JSON format (run with --live).

The router normally sends plans to Groq first, so Gemma on Google AI Studio is only exercised on fallbacks; these
tests call each model directly so a broken key, retired model id or changed API shows up immediately.
"""

import pytest

from app.config import MODELS, PROVIDERS, Route, _usable
from app.llm import LLMError, chat_json

HOSTED = [m for m in MODELS.values() if m.provider != "ollama"]


@pytest.mark.live
@pytest.mark.parametrize("spec", HOSTED, ids=[m.id for m in HOSTED])
def test_model_returns_json(spec):
    if not PROVIDERS[spec.provider].configured:
        pytest.skip(f"no API key for {spec.provider}")
    try:
        res = chat_json(
            "You answer with JSON only.",
            'Give one typical breakfast in Lyon, France as {"dish": string, "kcal": number, "protein_g": number}.',
            route=Route("test", [spec], "direct"),
            max_tokens=600,
            temperature=0,
        )
    except LLMError as e:
        if e.status in (429, 503):
            pytest.xfail(f"{spec.label} busy on the free tier: {e}")  # capacity, not a broken integration
        raise
    assert res.model.id == spec.id
    assert isinstance(res.data.get("dish"), str) and res.data["dish"]
    assert 50 <= float(res.data.get("kcal", 0)) <= 1500


@pytest.mark.live
def test_local_gemma_if_installed():
    spec = MODELS["gemma-local"]
    if not _usable(spec):
        pytest.skip("Ollama with the local Gemma model isn't installed")
    res = chat_json("JSON only.", 'Return {"ok": true}.', route=Route("test", [spec], "direct"), max_tokens=50)
    assert res.data.get("ok") is True
