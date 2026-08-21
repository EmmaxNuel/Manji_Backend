"""
Manji AI provider abstraction.

The rest of the application talks to a ``ChatProvider`` interface and never to
a specific vendor SDK, so providers can be swapped by changing
``AI_CHAT_PROVIDER`` in the environment (no code changes).

Supported providers (Phase 4):
- ``openai``    – any OpenAI-compatible ``/chat/completions`` endpoint (OpenAI,
                  Ollama, Together, …).
- ``openrouter``– OpenRouter (https://openrouter.ai/api/v1), keyed off
                  ``OPENROUTER_API_KEY``.
- ``gemini``    – Google Gemini REST API, keyed off ``GEMINI_API_KEY``.

When ``AI_CHAT_FALLBACK_PROVIDER`` is set, ``get_chat_provider()`` returns a
``FallbackChatProvider`` that tries the primary provider and, if it raises
``AIError``, transparently retries the turn on the fallback provider — so a
provider outage never surfaces as a hard failure to the creator. The fallback
behaviour lives once, in this abstraction, and every feature (chat, ideas,
outlines, …) inherits it automatically.
"""

import time
from abc import ABC, abstractmethod

import requests
from django.conf import settings

from apps.stories.ai_service import AIError

TIMEOUT = 120  # seconds, per HTTP call

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_SAFETY_BLOCKLIST = (
    ("HARM_CATEGORY_HARASSMENT", "BLOCK_NONE"),
    ("HARM_CATEGORY_HATE_SPEECH", "BLOCK_NONE"),
    ("HARM_CATEGORY_SEXUALLY_EXPLICIT", "BLOCK_NONE"),
    ("HARM_CATEGORY_DANGEROUS_CONTENT", "BLOCK_NONE"),
)


class ChatResult:
    """Normalised output from any chat provider."""

    def __init__(self, content, model, tokens_used=0, processing_time=0.0):
        self.content = content
        self.model = model
        self.tokens_used = tokens_used
        self.processing_time = processing_time


class ChatProvider(ABC):
    """Interface implemented by every chat/text-generation provider."""

    name = "base"
    model = ""

    @abstractmethod
    def complete(self, messages, max_tokens=800, temperature=0.7):
        """
        messages: list of {"role": "system"|"user"|"assistant", "content": str}
        Returns a ChatResult. Raises AIError on failure.
        """


class OpenAICompatibleChatProvider(ChatProvider):
    """Calls any OpenAI-compatible /chat/completions endpoint."""

    name = "openai"

    def __init__(self):
        self.model = settings.AI_CHAT_MODEL or settings.AI_TEXT_MODEL

    def complete(self, messages, max_tokens=800, temperature=0.7):
        base_url = settings.AI_TEXT_BASE_URL.rstrip("/")
        api_key = settings.AI_TEXT_API_KEY

        if not base_url or not self.model:
            raise AIError("AI_TEXT_BASE_URL / AI_CHAT_MODEL are not configured.")
        if api_key == "" and base_url.startswith("https://api.openai.com"):
            raise AIError(
                "Text generation is not configured. Set AI_TEXT_API_KEY in the "
                "backend .env file (or point AI_TEXT_BASE_URL at a local "
                "OpenAI-compatible server such as Ollama)."
            )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start = time.monotonic()
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=TIMEOUT,
                )
                if resp.status_code != 200:
                    last_err = AIError(
                        f"Text generation API error ({resp.status_code}): {resp.text[:500]}"
                    )
                    if resp.status_code in (401, 403, 402):
                        raise last_err
                else:
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content")
                    if content:
                        tokens = int(data.get("usage", {}).get("total_tokens", 0))
                        return ChatResult(
                            content.strip(),
                            self.model,
                            tokens_used=tokens,
                            processing_time=time.monotonic() - start,
                        )
                    last_err = AIError("The AI returned an empty response. Please try again.")
            except AIError:
                raise
            except Exception as exc:  # network errors
                last_err = exc
            time.sleep(1.5 * (attempt + 1))

        raise last_err or AIError("AI text generation failed. Please try again.")


class OpenRouterChatProvider(OpenAICompatibleChatProvider):
    """OpenRouter's OpenAI-compatible endpoint, keyed off OPENROUTER_API_KEY."""

    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"

    def __init__(self):
        self.model = settings.AI_OPENROUTER_MODEL or "openai/gpt-4o-mini"
        self.api_key = settings.OPENROUTER_API_KEY

    def complete(self, messages, max_tokens=800, temperature=0.7):
        if not self.api_key:
            raise AIError(
                "OpenRouter is not configured. Set OPENROUTER_API_KEY in the "
                "backend .env file."
            )
        base_url = self.base_url.rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start = time.monotonic()
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=TIMEOUT,
                )
                if resp.status_code != 200:
                    last_err = AIError(
                        f"OpenRouter API error ({resp.status_code}): {resp.text[:500]}"
                    )
                    if resp.status_code in (401, 403, 402):
                        raise last_err
                else:
                    data = resp.json()
                    content = data["choices"][0]["message"].get("content")
                    if content:
                        tokens = int(data.get("usage", {}).get("total_tokens", 0))
                        return ChatResult(
                            content.strip(),
                            self.model,
                            tokens_used=tokens,
                            processing_time=time.monotonic() - start,
                        )
                    last_err = AIError("The AI returned an empty response. Please try again.")
            except AIError:
                raise
            except Exception as exc:  # network errors
                last_err = exc
            time.sleep(1.5 * (attempt + 1))

        raise last_err or AIError("OpenRouter text generation failed. Please try again.")


class GeminiChatProvider(ChatProvider):
    """Google Gemini via the REST ``generateContent`` endpoint.

    Uses ``GEMINI_API_KEY`` and ``AI_GEMINI_MODEL``. Messages are converted
    from the shared OpenAI-style shape (roles ``system``/``user``/``assistant``)
    into Gemini's ``contents`` / ``systemInstruction`` shape.
    """

    name = "gemini"

    def __init__(self):
        self.model = settings.AI_GEMINI_MODEL or "gemini-1.5-flash"
        self.api_key = settings.GEMINI_API_KEY

    def _build_contents(self, messages):
        system_parts = []
        contents = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role in ("assistant", "model"):
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})
        return contents, system_parts

    def complete(self, messages, max_tokens=800, temperature=0.7):
        if not self.api_key:
            raise AIError(
                "Gemini is not configured. Set GEMINI_API_KEY in the backend .env file."
            )
        contents, system_parts = self._build_contents(messages)
        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        payload["safetySettings"] = [
            {"category": category, "threshold": threshold}
            for category, threshold in GEMINI_SAFETY_BLOCKLIST
        ]

        url = (
            f"{GEMINI_BASE_URL}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )

        start = time.monotonic()
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    timeout=TIMEOUT,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    last_err = AIError(
                        f"Gemini API error ({resp.status_code}): {resp.text[:500]}"
                    )
                    if resp.status_code in (401, 403, 400):
                        raise last_err
                else:
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        text = "".join(part.get("text", "") for part in parts).strip()
                        if text:
                            tokens = int(
                                data.get("usageMetadata", {}).get("totalTokenCount", 0)
                            )
                            return ChatResult(
                                text,
                                self.model,
                                tokens_used=tokens,
                                processing_time=time.monotonic() - start,
                            )
                        last_err = AIError(
                            f"Gemini blocked the request: {data.get('promptFeedback')}"
                        )
                    else:
                        last_err = AIError(
                            "Gemini returned no candidates. "
                            f"{data.get('promptFeedback') or 'Please try again.'}"
                        )
            except AIError:
                raise
            except Exception as exc:  # network errors
                last_err = exc
            time.sleep(1.5 * (attempt + 1))

        raise last_err or AIError("Gemini text generation failed. Please try again.")


class FallbackChatProvider(ChatProvider):
    """Tries the primary provider and falls back to a secondary on AIError.

    ``last_provider`` records which provider actually served the last turn so
    callers can audit/log the real vendor that was used.
    """

    name = "fallback"
    model = ""

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.last_provider = primary
        self.name = primary.name
        self.model = primary.model

    def complete(self, messages, max_tokens=800, temperature=0.7):
        self.last_provider = self.primary
        try:
            return self.primary.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )
        except AIError:
            self.last_provider = self.fallback
            return self.fallback.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )


class EmbeddingProvider(ABC):
    """Interface for vector embeddings. Implemented in a later phase."""

    @abstractmethod
    def embed(self, text):
        ...


class ImageProvider(ABC):
    """Interface for image generation. Phase 4 reuses apps.stories providers."""

    @abstractmethod
    def generate(self, prompt):
        ...


_CHAT_PROVIDERS = {
    "openai": OpenAICompatibleChatProvider,
    "openrouter": OpenRouterChatProvider,
    "gemini": GeminiChatProvider,
}


def _build_provider(name):
    cls = _CHAT_PROVIDERS.get(name)
    if cls is None:
        raise AIError(
            f"Unknown chat provider '{name}'. "
            f"Supported: {', '.join(sorted(_CHAT_PROVIDERS))}."
        )
    return cls()


def get_chat_provider(name=None):
    """Resolve the configured chat provider, wrapping it in a fallback chain
    when ``AI_CHAT_FALLBACK_PROVIDER`` names a second provider. Unknown names
    raise AIError."""
    name = (name or settings.AI_CHAT_PROVIDER).lower()
    fallback_name = (settings.AI_CHAT_FALLBACK_PROVIDER or "").lower()
    primary = _build_provider(name)
    if fallback_name and fallback_name != name:
        return FallbackChatProvider(primary, _build_provider(fallback_name))
    return primary