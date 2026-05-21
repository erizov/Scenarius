"""LLM providers: Ollama first, OpenAI fallback."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class LLMUnavailableError(RuntimeError):
    """No LLM provider is configured or reachable."""


@dataclass
class LLMResult:
    """Generated text and provider metadata."""

    text: str
    provider: str
    model: str


def _ollama_available(client: httpx.Client) -> bool:
    try:
        response = client.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=3.0,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _generate_ollama(prompt: str, client: httpx.Client) -> LLMResult:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": settings.llm_max_tokens},
    }
    response = client.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    text = (data.get("response") or "").strip()
    if not text:
        raise LLMUnavailableError("Ollama returned empty response")
    return LLMResult(text=text, provider="ollama", model=settings.ollama_model)


def _generate_openai(prompt: str) -> LLMResult:
    if not settings.openai_api_key:
        raise LLMUnavailableError("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMUnavailableError(
            "Install openai package: pip install scenarius[llm]",
        ) from exc

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.llm_max_tokens,
        temperature=0.8,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise LLMUnavailableError("OpenAI returned empty response")
    return LLMResult(
        text=text,
        provider="openai",
        model=settings.openai_model,
    )


def select_provider(client: httpx.Client | None = None) -> str:
    """Pick provider according to settings and availability."""
    mode = settings.llm_provider.lower()
    owns_client = client is None
    if client is None:
        client = httpx.Client()
    try:
        if mode == "ollama":
            if _ollama_available(client):
                return "ollama"
            raise LLMUnavailableError("Ollama is not reachable")
        if mode == "openai":
            if settings.openai_api_key:
                return "openai"
            raise LLMUnavailableError("OPENAI_API_KEY is not set")
        if _ollama_available(client):
            return "ollama"
        if settings.openai_api_key:
            return "openai"
        raise LLMUnavailableError(
            "No LLM available. Start Ollama or set OPENAI_API_KEY.",
        )
    finally:
        if owns_client:
            client.close()


def _ollama_error_message(exc: httpx.HTTPError) -> str:
    """Build a user-facing hint for Ollama failures."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return (
            f"Ollama model '{settings.ollama_model}' not found. "
            f"Run: ollama pull {settings.ollama_model} "
            "or set OLLAMA_MODEL in .env (ollama list)."
        )
    return (
        "Ollama generation failed. Check ollama serve and OLLAMA_MODEL in .env."
    )


def generate_text(prompt: str) -> LLMResult:
    """Generate story text using configured provider strategy."""
    with httpx.Client() as client:
        provider = select_provider(client)
        if provider == "ollama":
            try:
                return _generate_ollama(prompt, client)
            except httpx.HTTPError as exc:
                logger.warning("llm.ollama_failed", error=str(exc))
                if settings.llm_provider.lower() == "ollama":
                    raise LLMUnavailableError(
                        _ollama_error_message(exc),
                    ) from exc
                if settings.openai_api_key:
                    return _generate_openai(prompt)
                raise LLMUnavailableError(
                    _ollama_error_message(exc),
                ) from exc
        return _generate_openai(prompt)
